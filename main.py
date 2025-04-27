import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncpg
import itertools
from discord import Embed
import os

TOKEN = "MTM2NDYyMTI4NDYyNDgyNjQ4OQ.G_D73O.CkjCDjNYYEFpg1yXr8LQs9o5cI8Cangn6Rxn3U"
OWNER_ROLE_ID = 1364134027585523772
LOG_ID = 1365709885693493318

DATABASE_URL = os.getenv("DATABASE_URL")  # Railway te donnera DATABASE_URL

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- DATABASE SETUP ---
async def setup_database():
    bot.db = await asyncpg.create_pool(DATABASE_URL)
    async with bot.db.acquire() as connection:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS directories (
                id SERIAL PRIMARY KEY,
                channel_id BIGINT UNIQUE,
                intro TEXT,
                outro TEXT,
                message_id BIGINT
            );
        """)
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id SERIAL PRIMARY KEY,
                position INTEGER,
                emoji TEXT,
                name TEXT,
                link TEXT,
                comment TEXT
            );
        """)

# --- ROLE CHECK ---
async def has_role_by_id(interaction: discord.Interaction, role_id: int):
    role = discord.utils.get(interaction.guild.roles, id=role_id)
    return role in interaction.user.roles if role else False

# --- STATUS ROTATION ---
statuts = [
    "🏷️ des TAG EXCLUSIF",
    "🗣️ UN SERVEUR ACTIF",
    "🌐 UN SERVEUR INTERNATIONNAL",
    "🔗 Filial de SERVER'S HUB"
]
status_cycle = itertools.cycle(statuts)

@tasks.loop(seconds=10)
async def changer_status():
    activity = discord.Streaming(name=next(status_cycle), url="https://twitch.tv/hvk_mairox")
    await bot.change_presence(activity=activity)

# --- COMMANDS ---
@bot.tree.command(name="news_msg", description="📨 | ENVOIE LA LISTE DES TAGS")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def news_msg(interaction: discord.Interaction, intro: str, outro: str):
    await interaction.response.defer()
    async with bot.db.acquire() as connection:
        channel_id = interaction.channel.id
        message = await interaction.channel.send("Création du répertoire...")
        await connection.execute("""
            INSERT INTO directories (channel_id, intro, outro, message_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (channel_id) DO UPDATE SET intro = EXCLUDED.intro, outro = EXCLUDED.outro, message_id = EXCLUDED.message_id;
        """, channel_id, intro, outro, message.id)
    await refresh_all_directories()
    await interaction.followup.send("Répertoire créé et synchronisé ✅", ephemeral=True)

@bot.tree.command(name="tag_add", description="➕ | Ajouter un tag")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def tag_add(interaction: discord.Interaction, name: str, emoji: str, position: int, link: str, comment: str = None):
    await interaction.response.defer()
    async with bot.db.acquire() as connection:
        await connection.execute("UPDATE tags SET position = position + 1 WHERE position >= $1", position)
        await connection.execute("""
            INSERT INTO tags (position, emoji, name, link, comment)
            VALUES ($1, $2, $3, $4, $5)
        """, position, emoji, name, link, comment)
    await refresh_all_directories()
    await interaction.followup.send(f"Tag **{name}** ajouté ✅", ephemeral=True)

@bot.tree.command(name="remove_tag", description="🗑️ | Supprimer un tag existant")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def remove_tag(interaction: discord.Interaction, position: int):
    await interaction.response.defer()
    async with bot.db.acquire() as connection:
        tag = await connection.fetchrow("SELECT * FROM tags WHERE position = $1", position)
        if not tag:
            await interaction.followup.send("❌ Aucun tag trouvé à cette position.", ephemeral=True)
            return
        await connection.execute("DELETE FROM tags WHERE position = $1", position)
        await connection.execute("UPDATE tags SET position = position - 1 WHERE position > $1", position)
    await refresh_all_directories()
    await interaction.followup.send(f"✅ Tag position **{position}** supprimé.", ephemeral=True)

@bot.tree.command(name="tag", description="📦 | Livrée le Liens d'un TAGS")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def show_tags(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    async with bot.db.acquire() as connection:
        tags = await connection.fetch("SELECT id, emoji, name, link FROM tags ORDER BY position ASC")
    if not tags:
        await interaction.followup.send("Aucun tag disponible ❌")
        return

    class TagButton(discord.ui.Button):
        def __init__(self, tag_id, emoji, name, link):
            super().__init__(label=name, emoji=emoji, style=discord.ButtonStyle.primary)
            self.tag_link = link

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message(self.tag_link, ephemeral=False)

    view = discord.ui.View()
    for tag in tags:
        view.add_item(TagButton(tag['id'], tag['emoji'], tag['name'], tag['link']))
    await interaction.followup.send("Voici tous les tags disponibles :", view=view)

@bot.tree.command(name="tag_edit", description=" ✏️| Modifier un tag existant")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def tag_edit(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    async with bot.db.acquire() as connection:
        tags = await connection.fetch("SELECT id, position, emoji, name FROM tags ORDER BY position ASC")
    if not tags:
        await interaction.followup.send("Aucun tag à modifier ❌")
        return

    class EditButton(discord.ui.Button):
        def __init__(self, tag_id, name):
            super().__init__(label=name, style=discord.ButtonStyle.secondary)
            self.tag_id = tag_id

        async def callback(self, interaction: discord.Interaction):
            modal = EditTagModal(self.tag_id)
            await interaction.response.send_modal(modal)

    view = discord.ui.View()
    for tag in tags:
        view.add_item(EditButton(tag['id'], f"{tag['emoji']} {tag['name']}"))
    await interaction.followup.send("Sélectionnez un tag à modifier :", view=view)

class EditTagModal(discord.ui.Modal, title="Modifier le tag"):
    new_name = discord.ui.TextInput(label="Nouveau nom", required=False)
    new_emoji = discord.ui.TextInput(label="Nouvel emoji", required=False)
    new_link = discord.ui.TextInput(label="Nouveau lien", required=False)
    new_comment = discord.ui.TextInput(label="Nouveau commentaire", required=False)

    def __init__(self, tag_id):
        super().__init__()
        self.tag_id = tag_id

    async def on_submit(self, interaction: discord.Interaction):
        async with bot.db.acquire() as connection:
            tag = await connection.fetchrow("SELECT position, emoji, name, link, comment FROM tags WHERE id = $1", self.tag_id)
            if not tag:
                await interaction.response.send_message("❌ Tag introuvable.", ephemeral=True)
                return
            await connection.execute("""
                UPDATE tags SET name = $1, emoji = $2, link = $3, comment = $4
                WHERE id = $5
            """,
            self.new_name.value or tag['name'],
            self.new_emoji.value or tag['emoji'],
            self.new_link.value or tag['link'],
            self.new_comment.value or tag['comment'],
            self.tag_id)
        await refresh_all_directories()
        await interaction.response.send_message("✅ Tag modifié avec succès.", ephemeral=True)

# --- UTILS ---
async def refresh_all_directories():
    async with bot.db.acquire() as connection:
        tags = await connection.fetch("SELECT * FROM tags ORDER BY position ASC")
        if not tags:
            print("Pas de tags à afficher.")
            return

        body = ""
        for tag in tags:
            body += f"## {tag['emoji']} {tag['name']}\n"
            if tag['comment']:
                body += f"*{tag['comment']}*\n"

        directories = await connection.fetch("SELECT channel_id, intro, outro, message_id FROM directories")
        for directory in directories:
            channel = bot.get_channel(directory['channel_id'])
            if not channel:
                print(f"⚠️ Channel ID {directory['channel_id']} introuvable.")
                continue
            try:
                message = await channel.fetch_message(directory['message_id'])
                await message.edit(content=f"{directory['intro']}\n\n{body}\n{directory['outro']}")
            except Exception as e:
                print(f"Erreur modification message : {e}")

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ {bot.user.name} est connecté et prêt !")
    await setup_database()
    changer_status.start()
    try:
        synced = await bot.tree.sync()
        print(f"🔃 {len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"Erreur de sync : {e}")

@bot.tree.command(name="tuto", description="🧐 | Dire au gens comment Installer un TAG")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def tuto(interaction: discord.Interaction):
    embed = Embed(
        title="Personnalisation du Profil",
        description="Voici comment personnaliser ton profil et sélectionner un tag.",
        color=0x3498db
    )
    embed.add_field(name="Étape 1", value="Rejoins le serveur et va dans la section profil.", inline=False)
    embed.add_field(name="Étape 2", value="Sélectionne ton tag préféré.", inline=False)
    embed.add_field(name="Étape 3", value="Ton tag est actif partout.", inline=False)
    embed.add_field(name="Note", value="N'oublie pas de mettre #📍〃preuve dans ton profil.", inline=False)
    embed.set_image(url="https://cdn.discordapp.com/attachments/1364488298873225248/1364488520801980416/image.png")
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
