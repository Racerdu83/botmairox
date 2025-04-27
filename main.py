import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import itertools
import json
from discord import Embed

TOKEN = "MTM2NDYyMTI4NDYyNDgyNjQ4OQ.G_D73O.CkjCDjNYYEFpg1yXr8LQs9o5cI8Cangn6Rxn3U"
OWNER_ROLE_ID = 1364134027585523772
LOG_ID = 1365709885693493318

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Fonction pour vérifier les rôles
async def has_role_by_id(interaction: discord.Interaction, role_id: int):
    role = discord.utils.get(interaction.guild.roles, id=role_id)
    if role and role in interaction.user.roles:
        return True
    return False

# Sauvegarde des tags dans un fichier JSON
async def backup_tags_to_file():
    async with aiosqlite.connect("tags.db") as db:
        cursor = await db.execute("SELECT position, emoji, name, link, comment FROM tags ORDER BY position ASC")
        tags = await cursor.fetchall()

    tag_list = []
    for tag in tags:
        position, emoji, name, link, comment = tag
        tag_list.append({
            "position": position,
            "emoji": emoji,
            "name": name,
            "link": link,
            "comment": comment
        })

    with open("tags_backup.json", "w", encoding="utf-8") as f:
        json.dump(tag_list, f, ensure_ascii=False, indent=4)

# Restauration des tags depuis le fichier JSON
async def restore_tags_from_file():
    try:
        with open("tags_backup.json", "r", encoding="utf-8") as f:
            tag_list = json.load(f)

        async with aiosqlite.connect("tags.db") as db:
            await db.execute("DELETE FROM tags")  # Vide la table existante
            for tag in tag_list:
                await db.execute("""
                    INSERT INTO tags (position, emoji, name, link, comment)
                    VALUES (?, ?, ?, ?, ?)
                """, (tag["position"], tag["emoji"], tag["name"], tag["link"], tag["comment"]))
            await db.commit()
    except FileNotFoundError:
        print("⚠️ Aucun fichier de sauvegarde trouvé.")

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

# Statuts tournants
statuts = [
    "🏷️ des TAG EXCLUSIF",
    "🗣️ UN SERVEUR ACTIF",
    "🌐 UN SERVEUR INTERNATIONNAL",
    "🔗 Filial de SEVERVER'S HUB"
]
status_cycle = itertools.cycle(statuts)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} est prêt !")
    await setup_database()
    await backup_tags_to_file()
    try:
        synced = await bot.tree.sync()
        print(f"🔃 {len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"Erreur de sync : {e}")
    changer_status.start()

@tasks.loop(seconds=10)
async def changer_status():
    activity = discord.Streaming(
        name=next(status_cycle),
        url="https://twitch.tv/hvk_mairox"
    )
    await bot.change_presence(activity=activity)

# Commande pour envoyer un embed de news
@bot.tree.command(name="news_msg", description="📢 | Envoyer un message de news (admin seulement)")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def news_msg(interaction: discord.Interaction, titre: str, description: str):
    await interaction.response.defer(ephemeral=True)
    embed = Embed(title=titre, description=description, color=discord.Color.blue())
    await interaction.channel.send(embed=embed)
    await interaction.followup.send("✅ News envoyée.", ephemeral=True)

# Commande pour ajouter un tag
@bot.tree.command(name="tag_add", description="🏷️ | Ajouter un tag (admin seulement)")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def tag_add(interaction: discord.Interaction, position: int, emoji: str, name: str, link: str, comment: str):
    await interaction.response.defer(ephemeral=True)
    async with aiosqlite.connect("tags.db") as db:
        await db.execute("""
            INSERT INTO tags (position, emoji, name, link, comment)
            VALUES (?, ?, ?, ?, ?)
        """, (position, emoji, name, link, comment))
        await db.commit()
    await interaction.followup.send("✅ Tag ajouté avec succès.", ephemeral=True)

# Commande pour sauvegarder les tags
@bot.tree.command(name="backup_tags", description="💾 | Sauvegarder les tags dans un fichier (admin seulement)")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def backup_tags_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await backup_tags_to_file()
    await interaction.followup.send("✅ Tags sauvegardés dans `tags_backup.json`.", ephemeral=True)

# Commande pour restaurer les tags
@bot.tree.command(name="restore_tags", description="♻️ | Restaurer les tags depuis la sauvegarde (admin seulement)")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def restore_tags_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await restore_tags_from_file()
    await interaction.followup.send("✅ Tags restaurés depuis `tags_backup.json`.", ephemeral=True)

# Commande pour rafraîchir toutes les directories
@bot.tree.command(name="refresh_all_directories", description="🔄 | Rafraîchir toutes les directories (admin seulement)")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def refresh_all_directories(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    async with aiosqlite.connect("tags.db") as db:
        cursor = await db.execute("SELECT channel_id FROM directories")
        channels = await cursor.fetchall()

    for (channel_id,) in channels:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.purge()
            embed = discord.Embed(title="Répertoire", description="Liste mise à jour.", color=discord.Color.green())
            await channel.send(embed=embed)

    await interaction.followup.send("✅ Tous les directories ont été rafraîchis.", ephemeral=True)

# Commande tuto pour afficher un tuto embed
@bot.tree.command(name="tuto", description="📚 | Envoyer un tutoriel (admin seulement)")
@app_commands.check(lambda interaction: has_role_by_id(interaction, OWNER_ROLE_ID))
async def tuto(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(
        title="Comment utiliser le serveur",
        description="Bienvenue ! Voici comment naviguer dans notre serveur...",
        color=discord.Color.purple()
    )
    await interaction.channel.send(embed=embed)
    await interaction.followup.send("✅ Tutoriel envoyé.", ephemeral=True)

bot.run(TOKEN)
