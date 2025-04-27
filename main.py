import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncpg
import itertools
import os
from discord import Embed

TOKEN = "MTM2NDYyMTI4NDYyNDgyNjQ4OQ.G_D73O.CkjCDjNYYEFpg1yXr8LQs9o5cI8Cangn6Rxn3U"  # Ton token
OWNER_ROLE_ID = 1364134027585523772
LOG_ID = 1365709885693493318

DATABASE_URL = os.getenv("DATABASE_URL")  # Railway génère ça automatiquement

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.db = None  # On prépare la connexion

# DATABASE SETUP
async def setup_database():
    await bot.db.execute("""
        CREATE TABLE IF NOT EXISTS directories (
            id SERIAL PRIMARY KEY,
            channel_id BIGINT UNIQUE,
            intro TEXT,
            outro TEXT,
            message_id BIGINT
        );
    """)
    await bot.db.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id SERIAL PRIMARY KEY,
            position INTEGER,
            emoji TEXT,
            name TEXT,
            link TEXT,
            comment TEXT
        );
    """)

# Liste des statuts
statuts = [
    "🏷️ des TAG EXCLUSIF",
    "🗣️ UN SERVEUR ACTIF",
    "🌐 UN SERVEUR INTERNATIONNAL",
    "🔗 Filial de SEVERVER'S HUB"
]
status_cycle = itertools.cycle(statuts)

@bot.event
async def on_ready():
    print(f"✅ {bot.user.name} est connecté !")
    if bot.db is None:
        bot.db = await asyncpg.connect(DATABASE_URL)
    changer_status.start()
    await setup_database()
    try:
        synced = await bot.tree.sync()
        print(f"🔃 {len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"Erreur de sync : {e}")

@tasks.loop(seconds=10)
async def changer_status():
    activity = discord.Streaming(
        name=next(status_cycle),
        url="https://twitch.tv/hvk_mairox"
    )
    await bot.change_presence(activity=activity)

# Vérification du rôle
async def has_role_by_id(interaction: discord.Interaction, role_id: int):
    role = discord.utils.get(interaction.guild.roles, id=role_id)
    return role in interaction.user.roles if role else False

# ➕ Créer un répertoire
@bot.tree.command(name="news_msg", description="📨 | ENVOIE LA LISTE DES TAGS")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def news_msg(interaction: discord.Interaction, intro: str, outro: str):
    await interaction.response.defer()
    channel_id = interaction.channel.id
    message = await interaction.channel.send("Création du répertoire...")

    await bot.db.execute(
        "INSERT INTO directories (channel_id, intro, outro, message_id) VALUES ($1, $2, $3, $4) ON CONFLICT (channel_id) DO UPDATE SET intro = EXCLUDED.intro, outro = EXCLUDED.outro, message_id = EXCLUDED.message_id",
        channel_id, intro, outro, message.id
    )

    await refresh_all_directories()
    await interaction.followup.send("Répertoire créé et synchronisé ✅", ephemeral=True)

# ➕ Ajouter un tag
@bot.tree.command(name="tag_add", description="➕ | Ajouter un tag")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def tag_add(interaction: discord.Interaction, name: str, emoji: str, position: int, link: str, comment: str = None):
    await interaction.response.defer()
    await bot.db.execute("UPDATE tags SET position = position + 1 WHERE position >= $1", position)
    await bot.db.execute(
        "INSERT INTO tags (position, emoji, name, link, comment) VALUES ($1, $2, $3, $4, $5)",
        position, emoji, name, link, comment
    )

    await refresh_all_directories()
    await interaction.followup.send(f"Tag **{name}** ajouté ✅", ephemeral=True)

# ➖ Supprimer un tag
@bot.tree.command(name="remove_tag", description="🗑️ | Supprimer un tag existant")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def remove_tag(interaction: discord.Interaction, position: int):
    await interaction.response.defer()

    tag = await bot.db.fetchrow("SELECT * FROM tags WHERE position = $1", position)
    if not tag:
        await interaction.followup.send("❌ Aucun tag trouvé à cette position.", ephemeral=True)
        return

    await bot.db.execute("DELETE FROM tags WHERE position = $1", position)
    await bot.db.execute("UPDATE tags SET position = position - 1 WHERE position > $1", position)

    await refresh_all_directories()
    await interaction.followup.send(f"✅ Tag position **{position}** supprimé.", ephemeral=True)

# 📚 Voir les tags
@bot.tree.command(name="tag", description="📦 | Livrée le Liens d'un TAGS")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def show_tags(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    tags = await bot.db.fetch("SELECT id, emoji, name, link FROM tags ORDER BY position ASC")

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
        tag_id, emoji, name, link = tag
        view.add_item(TagButton(tag_id, emoji, name, link))

    await interaction.followup.send("Voici tous les tags disponibles :", view=view)

# 🛠️ Modifier un tag
@bot.tree.command(name="tag_edit", description="✏️ | Modifier un tag existant")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def tag_edit(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    tags = await bot.db.fetch("SELECT id, position, emoji, name FROM tags ORDER BY position ASC")

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
        tag_id, position, emoji, name = tag
        view.add_item(EditButton(tag_id, f"{emoji} {name}"))

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
        tag = await bot.db.fetchrow("SELECT position, emoji, name, link, comment FROM tags WHERE id = $1", self.tag_id)
        if not tag:
            await interaction.response.send_message("❌ Tag introuvable.", ephemeral=True)
            return

        await bot.db.execute("""
            UPDATE tags SET name = COALESCE($1, name), emoji = COALESCE($2, emoji),
                            link = COALESCE($3, link), comment = COALESCE($4, comment)
            WHERE id = $5
        """, self.new_name.value or None, self.new_emoji.value or None, self.new_link.value or None, self.new_comment.value or None, self.tag_id)

        await refresh_all_directories()
        await interaction.response.send_message("✅ Tag modifié avec succès.", ephemeral=True)

# --- UTILS ---
async def refresh_all_directories():
    tags = await bot.db.fetch("SELECT * FROM tags ORDER BY position ASC")

    body = ""
    for tag in tags:
        _, position, emoji, name, link, comment = tag
        body += f"## {emoji} {name}\n"
        if comment:
            body += f"*{comment}*\n"

    directories = await bot.db.fetch("SELECT channel_id, intro, outro, message_id FROM directories")

    for channel_id, intro, outro, message_id in directories:
        channel = bot.get_channel(channel_id)
        if not channel:
            continue
        try:
            msg = await channel.fetch_message(message_id)
            content = f"{intro}\n\n{body}\n{outro}"
            await msg.edit(content=content)
        except:
            continue

@bot.tree.command(name="tuto", description="🧐 | Dire aux gens comment installer un TAG")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def tuto(interaction: discord.Interaction):
    embed = Embed(
        title="Personnalisation du Profil",
        description="Voici comment personnaliser ton profil et sélectionner un tag.",
        color=0x3498db
    )
    embed.add_field(name="Étape 1", value="Rejoins le serveur.", inline=False)
    embed.add_field(name="Étape 2", value="Sélectionne le tag que tu souhaites.", inline=False)
    embed.add_field(name="Étape 3", value="Mets à jour ton profil avec le tag.", inline=False)
    embed.set_image(url="https://cdn.discordapp.com/attachments/1364488298873225248/1364488520801980416/image.png")

    await interaction.response.send_message(embed=embed, ephemeral=False)

bot.run(TOKEN)
