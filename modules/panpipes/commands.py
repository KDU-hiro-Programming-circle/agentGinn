"""Panpipes Discord commands and the #library channel image flow.

A post in #library with an image attachment is decoded for a barcode
and shown back with 貸出/返却/新規登録 buttons -- the button click is
what actually writes to the DB, not the post itself.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from shared import permissions
from shared.config import config as config_store
from shared.logger import get_logger

from . import isbn as isbn_lookup
from . import models, service

logger = get_logger(__name__)


class BookActionView(discord.ui.View):
    def __init__(self, isbn: str, info: isbn_lookup.BookInfo | None, actor_id: int, timeout: float = 180) -> None:
        super().__init__(timeout=timeout)
        self.isbn = isbn
        self.info = info
        self.actor_id = actor_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message("この操作は投稿者のみ行えます。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="貸出", style=discord.ButtonStyle.primary)
    async def borrow(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            borrow = await service.borrow_by_isbn(self.isbn, str(interaction.user.id))
        except service.PanpipesError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        await interaction.followup.send(f"貸出登録しました（返却期限: {borrow.due_at}）。", ephemeral=True)

    @discord.ui.button(label="返却", style=discord.ButtonStyle.secondary)
    async def return_book(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            await service.return_by_isbn(self.isbn, str(interaction.user.id))
        except service.PanpipesError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        await interaction.followup.send("返却登録しました。", ephemeral=True)

    @discord.ui.button(label="新規登録", style=discord.ButtonStyle.success)
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        if self.info is None:
            await interaction.followup.send(
                "書籍情報が見つかりませんでした。`/panpipes register` で手動登録してください。", ephemeral=True
            )
            return
        book = await service.register_from_lookup(self.isbn, self.info, str(interaction.user.id))
        await interaction.followup.send(f"『{book.title}』を登録しました。", ephemeral=True)


class PanpipesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    panpipes_group = app_commands.Group(name="panpipes", description="図書貸出管理")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        panpipes_cfg = config_store.load("panpipes")
        if message.channel.id != panpipes_cfg.get("library_channel_id"):
            return

        image_attachments = [a for a in message.attachments if (a.content_type or "").startswith("image/")]
        if not image_attachments:
            return

        image_bytes = await image_attachments[0].read()
        try:
            isbn, info = await service.identify_from_image(image_bytes)
        except service.PanpipesError as exc:
            await message.reply(str(exc))
            return
        except RuntimeError:
            await message.reply(
                "この環境ではバーコード読み取りが利用できません。`/panpipes register` で手動登録してください。"
            )
            return

        if info is not None:
            description = f"**{info.title}**\n{info.author or '著者不明'}\nISBN: {isbn}"
        else:
            description = f"ISBN: {isbn}（書籍情報は見つかりませんでした）"

        view = BookActionView(isbn, info, message.author.id)
        await message.reply(f"{description}\n\n貸出・返却・新規登録のいずれかを選択してください。", view=view)

    @panpipes_group.command(name="search", description="タイトル・著者・ISBNで検索")
    @app_commands.describe(query="検索キーワード")
    @permissions.require("panpipes")
    async def search(self, interaction: discord.Interaction, query: str) -> None:
        books = await models.search_books(query)
        if not books:
            await interaction.response.send_message("該当する本が見つかりませんでした。")
            return
        lines = [f"- {b.title} / {b.author or '著者不明'}（ISBN: {b.isbn or 'なし'}）" for b in books]
        await interaction.response.send_message("\n".join(lines))

    async def _title_autocomplete(self, current: str) -> list[app_commands.Choice[str]]:
        books = await models.search_books(current or "", limit=25)
        # Discord caps both choice name and value at 100 chars; titles (esp.
        # light novels) can run longer, so submit the book id instead of the
        # title text -- _resolve_book() below accepts either.
        return [app_commands.Choice(name=b.title[:100], value=str(b.id)) for b in books]

    async def _resolve_book(self, title: str) -> models.Book | None:
        """Resolve a /panpipes title argument: either a book id picked from
        autocomplete, or free-typed text matched via search_books()."""
        if title.isdigit():
            book = await models.get_book(int(title))
            if book is not None:
                return book
        books = await models.search_books(title, limit=1)
        return books[0] if books else None

    @panpipes_group.command(name="borrow", description="本を借りる")
    @app_commands.describe(title="本のタイトル")
    @permissions.require("panpipes")
    async def borrow(self, interaction: discord.Interaction, title: str) -> None:
        await interaction.response.defer(thinking=True)
        book = await self._resolve_book(title)
        if book is None:
            await interaction.followup.send("該当する本が見つかりませんでした。")
            return
        try:
            borrow = await service.borrow_book(book, str(interaction.user.id))
        except service.PanpipesError as exc:
            await interaction.followup.send(str(exc))
            return
        await interaction.followup.send(f"『{book.title}』を貸出登録しました（返却期限: {borrow.due_at}）。")

    @borrow.autocomplete("title")
    async def borrow_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._title_autocomplete(current)

    @panpipes_group.command(name="return", description="本を返却する")
    @app_commands.describe(title="本のタイトル")
    @permissions.require("panpipes")
    async def return_(self, interaction: discord.Interaction, title: str) -> None:
        await interaction.response.defer(thinking=True)
        book = await self._resolve_book(title)
        if book is None:
            await interaction.followup.send("該当する本が見つかりませんでした。")
            return
        try:
            await service.return_book(book, str(interaction.user.id))
        except service.PanpipesError as exc:
            await interaction.followup.send(str(exc))
            return
        await interaction.followup.send(f"『{book.title}』を返却登録しました。")

    @return_.autocomplete("title")
    async def return_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._title_autocomplete(current)

    @panpipes_group.command(name="history", description="本の貸出履歴を表示")
    @app_commands.describe(title="本のタイトル")
    @permissions.require("panpipes")
    async def history(self, interaction: discord.Interaction, title: str) -> None:
        book = await self._resolve_book(title)
        if book is None:
            await interaction.response.send_message("該当する本が見つかりませんでした。")
            return
        events = await models.book_history(book.id)
        if not events:
            await interaction.response.send_message("履歴がありません。")
            return
        lines = [f"`{e['created_at']}` {e['event_type']} by <@{e['actor_id']}>" for e in events]
        await interaction.response.send_message("\n".join(lines))

    @history.autocomplete("title")
    async def history_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._title_autocomplete(current)

    @panpipes_group.command(name="overdue", description="返却期限超過中の本を表示")
    @permissions.require("panpipes")
    async def overdue(self, interaction: discord.Interaction) -> None:
        overdue_rows = await models.list_overdue(service.today_iso())
        if not overdue_rows:
            await interaction.response.send_message("返却期限超過中の本はありません。")
            return
        lines = []
        for borrow in overdue_rows:
            book = await models.get_book(borrow.book_id)
            title = book.title if book else f"book_id={borrow.book_id}"
            lines.append(f"- 『{title}』 <@{borrow.borrower_id}>（期限: {borrow.due_at}）")
        await interaction.response.send_message("\n".join(lines))

    @panpipes_group.command(name="register", description="本を手動登録（ISBNまたはタイトル手入力）")
    @app_commands.describe(isbn="ISBN（分かる場合）", title="タイトル（ISBNで情報が引けない場合は必須）", author="著者（任意）")
    @permissions.require("panpipes")
    async def register(
        self,
        interaction: discord.Interaction,
        isbn: str | None = None,
        title: str | None = None,
        author: str | None = None,
    ) -> None:
        await interaction.response.defer(thinking=True)

        resolved_title = title
        resolved_author = author

        if isbn:
            existing = await models.get_book_by_isbn(isbn)
            if existing is not None:
                await interaction.followup.send(f"『{existing.title}』は既に登録済みです。")
                return
            if not resolved_title:
                info = await isbn_lookup.lookup(isbn)
                if info is not None:
                    resolved_title = info.title
                    resolved_author = resolved_author or info.author

        if not resolved_title:
            await interaction.followup.send(
                "ISBNから書籍情報を取得できませんでした。`title` を指定して手動登録してください。"
            )
            return

        book = await service.register_manual(
            isbn=isbn, title=resolved_title, author=resolved_author, registered_by=str(interaction.user.id)
        )
        await interaction.followup.send(f"『{book.title}』を登録しました。")
