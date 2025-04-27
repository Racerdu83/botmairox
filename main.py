import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncpg
import itertools
from discord import Embed
import os

TOKEN = os.getenv("DISCORD_TOKEN")  # protection token ✅

# Liste des utilisateurs autorisés
AUTHORIZED_USERS = [803209433022201866, 770642066534957116, 1347996811159408791]

# Infos PostgreSQL
DB_USER = os.getenv("PGUSER")
DB_PASSWORD = os.getenv("PGPASSWORD")
DB_DATABASE = os.getenv("PGDATABASE")
DB_HOST = os.getenv("PGHOST")
DB_PORT = os.getenv("PGPORT")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
db = None

async def connect_to_db():
    global db
    db = await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_DATABASE,
        host=DB_HOST,
        port=DB_PORT
    )
    print("✅ Connecté à PostgreSQL")

# --- STATUTS CYCLING ---
statuts = [
    "🏷️ des TAG EXCLUSIF",
    "🗣️ UN SERVEUR ACTIF",
    "🌐 UN SERVEUR INTERNATIONNAL",
    "🔗 Filial de SEVERVER'S HUB"
]
status_cycle = itertools.cycle(statuts)

@tasks.loop(seconds=10)
async def changer_status():
    activity = discord.Streaming(
        name=next(status_cycle),
        url="https://twitch.tv/hvk_mairox"
    )
    await bot.change_presence(activity=activity)

# --- DATABASE SETUP ---
async def setup_database():
    async with db.acquire() as connection:
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

# --- UTILITIES ---
async def has_permission(interaction: discord.Interaction):
    return interaction.user.id in AUTHORIZED_USERS

async def refresh_all_directories():
    async with db.acquire() as connection:
        tags = await connection.fetch("SELECT * FROM tags ORDER BY position ASC")

        body = ""
        for tag in tags:
            body += f"## {tag['emoji']} {tag['name']}\n"
            if tag['comment']:
                body += f"*{tag['comment']}*\n"

        directories = await connection.fetch("SELECT channel_id, intro, outro, message_id FROM directories")

        for directory in directories:
            channel = bot.get_channel(directory['channel_id'])
            if channel:
                try:
                    msg = await channel.fetch_message(directory['message_id'])
                    content = f"{directory['intro']}\n\n{body}\n{directory['outro']}"
                    await msg.edit(content=content)
                except Exception as e:
                    print(f"Erreur de refresh : {e}")

# --- COMMANDS ---

@bot.tree.command(name="news_msg", description="📨 | ENVOIE LA LISTE DES TAGS")
@app_commands.check(has_permission)
async def news_msg(interaction: discord.Interaction, intro: str, outro: str):
    await interaction.response.defer()
    async with db.acquire() as connection:
        channel_id = interaction.channel.id
        message = await interaction.channel.send("Création du répertoire...")

        await connection.execute("""
            INSERT INTO directories (channel_id, intro, outro, message_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (channel_id) DO UPDATE
            SET intro = EXCLUDED.intro, outro = EXCLUDED.outro, message_id = EXCLUDED.message_id;
        """, channel_id, intro, outro, message.id)

    await refresh_all_directories()
    await interaction.followup.send("Répertoire créé et synchronisé ✅", ephemeral=True)

@bot.tree.command(name="tag_add", description="➕ | Ajouter un tag")
@app_commands.check(has_permission)
async def tag_add(interaction: discord.Interaction, name: str, emoji: str, position: int, link: str, comment: str = None):
    await interaction.response.defer()

    # Anti-duplication de lien
    async with db.acquire() as connection:
        existing_tag = await connection.fetchrow("SELECT * FROM tags WHERE link = $1", link)
        if existing_tag:
            await interaction.followup.send("❌ Ce lien est déjà enregistré dans un tag existant.", ephemeral=True)
            return

        await connection.execute("UPDATE tags SET position = position + 1 WHERE position >= $1", position)
        await connection.execute("""
            INSERT INTO tags (position, emoji, name, link, comment)
            VALUES ($1, $2, $3, $4, $5)
        """, position, emoji, name, link, comment)

    await refresh_all_directories()
    await interaction.followup.send(f"Tag **{name}** ajouté ✅", ephemeral=True)

@bot.tree.command(name="remove_tag", description="🗑️ | Supprimer un tag existant")
@app_commands.check(has_permission)
async def remove_tag(interaction: discord.Interaction, position: int):
    await interaction.response.defer()
    async with db.acquire() as connection:
        tag = await connection.fetchrow("SELECT * FROM tags WHERE position = $1", position)
        if not tag:
            await interaction.followup.send("❌ Aucun tag trouvé à cette position.", ephemeral=True)
            return

        await connection.execute("DELETE FROM tags WHERE position = $1", position)
        await connection.execute("UPDATE tags SET position = position - 1 WHERE position > $1", position)

    await refresh_all_directories()
    await interaction.followup.send(f"✅ Tag position **{position}** supprimé.", ephemeral=True)

@bot.tree.command(name="tag", description="📦 | Livrée le Liens d'un TAGS")
@app_commands.check(has_permission)
async def show_tags(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    async with db.acquire() as connection:
        tags = await connection.fetch("SELECT id, emoji, name, link FROM tags ORDER BY position ASC")

    if not tags:
        await interaction.followup.send("Aucun tag disponible ❌")
        return

    class TagButton(discord.ui.Button):
        def __init__(self, tag_id, emoji, name, link):
            super().__init__(label=name, emoji=emoji, style=discord.ButtonStyle.primary)
            self.tag_link = link

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message(f"{self.tag_link}", ephemeral=False)

    view = discord.ui.View()
    for tag in tags:
        view.add_item(TagButton(tag['id'], tag['emoji'], tag['name'], tag['link']))

    await interaction.followup.send("Voici tous les tags disponibles :", view=view)

@bot.tree.command(name="tuto", description="🧐 | Dire aux gens comment Installer un TAG")
async def tuto(interaction: discord.Interaction):
    embed = Embed(
        title="Personnalisation du Profil",
        description="Voici comment personnaliser ton profil et sélectionner un tag. Suis les étapes ci-dessous pour activer ton tag partout !",
        color=0x3498db
    )

    embed.add_field(name="Étape 1", value="Rejoins le serveur et accède à la section de personnalisation de ton profil.", inline=False)
    embed.add_field(name="Étape 2", value="Sélectionne le tag que tu souhaites dans la liste des options disponibles.", inline=False)
    embed.add_field(name="Étape 3", value="Une fois sélectionné, ton tag sera activé partout.", inline=False)
    embed.add_field(name="Note", value="Pense à mettre à jour ton profil avec le tag #📍〃preuve pour le rendre visible !", inline=False)

    embed.set_image(url="https://cdn.discordapp.com/attachments/1364488298873225248/1364488520801980416/image.png")

    await interaction.response.send_message(embed=embed, ephemeral=False)

# --- BOT EVENTS ---

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user}")
    await connect_to_db()
    await setup_database()
    changer_status.start()
    try:
        synced = await bot.tree.sync()
        print(f"🔃 {len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"Erreur de sync : {e}")

bot.run(TOKEN)
