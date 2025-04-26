import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import itertools
from discord import Embed

TOKEN = "MTM2NDYyMTI4NDYyNDgyNjQ4OQ.G_D73O.CkjCDjNYYEFpg1yXr8LQs9o5cI8Cangn6Rxn3U"  # <-- Mets ton token ici
OWNER_ROLE_ID = 1364134027585523772  # <-- ID du rôle du propriétaire
LOG_ID = 1365709885693493318

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ {bot.user.name} est connecté et surveille les tickets en temps réel !")
    bot.loop.create_task(send_keep_alive_message())

# Liste des statuts à afficher
statuts = [
    "🏷️ des TAG EXCLUSIF",
    "🗣️ UN SERVEUR ACTIF",
    "🌐 UN SERVEUR INTERNATIONNAL",
    "🔗 Filial de SEVERVER'S HUB"
]

# Cycle pour faire tourner les statuts
status_cycle = itertools.cycle(statuts)

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")
    changer_status.start()

@tasks.loop(seconds=10)
async def changer_status():
    activity = discord.Streaming(
        name=next(status_cycle),
        url="https://twitch.tv/hvk_mairox"
    )
    await bot.change_presence(activity=activity)

# DATABASE SETUP
async def setup_database():
    async with aiosqlite.connect("tags.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS directories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER UNIQUE,
                intro TEXT,
                outro TEXT,
                message_id INTEGER
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position INTEGER,
                emoji TEXT,
                name TEXT,
                link TEXT,
                comment TEXT
            );
        """)
        await db.commit()

# Vérification du rôle du propriétaire
async def has_role_by_id(interaction: discord.Interaction, role_id: int):
    """Vérifie si l'utilisateur a un rôle avec une ID spécifique."""
    role = discord.utils.get(interaction.guild.roles, id=role_id)
    if role and role in interaction.user.roles:
        return True
    return False

# --- COMMANDES ---

# ➕ Créer un répertoire
@bot.tree.command(name="news_msg", description="📨 | ENVOIE LA LISTE DES TAGS")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def news_msg(interaction: discord.Interaction, intro: str, outro: str):
    await interaction.response.defer()

    async with aiosqlite.connect("tags.db") as db:
        channel_id = interaction.channel.id
        message = await interaction.channel.send("Création du répertoire...")

        await db.execute(
            "INSERT OR REPLACE INTO directories (channel_id, intro, outro, message_id) VALUES (?, ?, ?, ?)",
            (channel_id, intro, outro, message.id)
        )
        await db.commit()

    await refresh_all_directories()
    await interaction.followup.send("Répertoire créé et synchronisé ✅", ephemeral=True)

# ➕ Ajouter un tag
@bot.tree.command(name="tag_add", description="➕ | Ajouter un tag")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def tag_add(interaction: discord.Interaction, name: str, emoji: str, position: int, link: str, comment: str = None):
    await interaction.response.defer()

    async with aiosqlite.connect("tags.db") as db:
        await db.execute("UPDATE tags SET position = position + 1 WHERE position >= ?", (position,))
        await db.execute(
            "INSERT INTO tags (position, emoji, name, link, comment) VALUES (?, ?, ?, ?, ?)",
            (position, emoji, name, link, comment)
        )
        await db.commit()

    await refresh_all_directories()
    await interaction.followup.send(f"Tag **{name}** ajouté ✅", ephemeral=True)

# ➖ Supprimer un tag
@bot.tree.command(name="remove_tag", description="🗑️ | Supprimer un tag existant")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def remove_tag(interaction: discord.Interaction, position: int):
    await interaction.response.defer()

    async with aiosqlite.connect("tags.db") as db:
        cursor = await db.execute("SELECT * FROM tags WHERE position = ?", (position,))
        tag = await cursor.fetchone()

        if not tag:
            await interaction.followup.send("❌ Aucun tag trouvé à cette position.", ephemeral=True)
            return

        await db.execute("DELETE FROM tags WHERE position = ?", (position,))
        await db.execute("UPDATE tags SET position = position - 1 WHERE position > ?", (position,))
        await db.commit()

    await refresh_all_directories()
    await interaction.followup.send(f"✅ Tag position **{position}** supprimé.", ephemeral=True)

# 📚 Voir les tags avec boutons
@bot.tree.command(name="tag", description="📦 | Livrée le Liens d'un TAGS")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def show_tags(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    async with aiosqlite.connect("tags.db") as db:
        cursor = await db.execute("SELECT id, emoji, name, link FROM tags ORDER BY position ASC")
        tags = await cursor.fetchall()

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
@bot.tree.command(name="tag_edit", description=" ✏️| Modifier un tag existant")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def tag_edit(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    async with aiosqlite.connect("tags.db") as db:
        cursor = await db.execute("SELECT id, position, emoji, name FROM tags ORDER BY position ASC")
        tags = await cursor.fetchall()

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
        async with aiosqlite.connect("tags.db") as db:
            cursor = await db.execute("SELECT position, emoji, name, link, comment FROM tags WHERE id = ?", (self.tag_id,))
            tag = await cursor.fetchone()
            if not tag:
                await interaction.response.send_message("❌ Tag introuvable.", ephemeral=True)
                return

            position, emoji, name, link, comment = tag

            await db.execute("""
                UPDATE tags SET name = ?, emoji = ?, link = ?, comment = ?
                WHERE id = ?
            """, (
                self.new_name.value or name,
                self.new_emoji.value or emoji,
                self.new_link.value or link,
                self.new_comment.value or comment,
                self.tag_id
            ))
            await db.commit()

        await refresh_all_directories()
        await interaction.response.send_message("✅ Tag modifié avec succès.", ephemeral=True)

# --- UTILS ---

async def refresh_all_directories():
    async with aiosqlite.connect("tags.db") as db:
        cursor = await db.execute("SELECT * FROM tags ORDER BY position ASC")
        tags = await cursor.fetchall()

        body = ""
        for tag in tags:
            _, position, emoji, name, link, comment = tag
            body += f"## {emoji} {name}\n"
            if comment:
                body += f"*{comment}*\n"

        cursor = await db.execute("SELECT channel_id, intro, outro, message_id FROM directories")
        directories = await cursor.fetchall()

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

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ {bot.user} est prêt !")
    await setup_database()
    try:
        synced = await bot.tree.sync()
        print(f"🔃 {len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"Erreur de sync : {e}")
@bot.tree.command(name="tuto", description="🧐 | Dire au gens comment Installer un TAG")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def show_tags(interaction: discord.Interaction):
    embed = Embed(
        title="Personnalisation du Profil",
        description="Voici comment personnaliser ton profil et sélectionner un tag. Suis les étapes ci-dessous pour activer ton tag partout !",
        color=0x3498db  # Bleu
    )

    embed.add_field(name="Étape 1", value="Rejoins le serveur et accède à la section de personnalisation de ton profil.", inline=False)
    embed.add_field(name="Étape 2", value="Sélectionne le tag que tu souhaites dans la liste des options disponibles.", inline=False)
    embed.add_field(name="Étape 3", value="Une fois sélectionné, ton tag sera activé partout.", inline=False)
    embed.add_field(name="Note", value="Pense à mettre à jour ton profil avec le tag #📍〃preuve pour le rendre visible !", inline=False)

    embed.set_image(url="https://cdn.discordapp.com/attachments/1364488298873225248/1364488520801980416/image.png?ex=680dcef6&is=680c7d76&hm=cf330017908c789e26a0dd1eed3832831a5270ce6c9b7ecf0b4f94cb7bcd6cb1&")

    await interaction.response.send_message(embed=embed, ephemeral=False)
bot.run(TOKEN)
