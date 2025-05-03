import discord
from discord.ext import commands
from discord import app_commands
import json
import re
import os

GUILD_ID = 1364133729114652742 #Remplace par ton ID de serveur
TAG_CHANNEL_ID = 1367803606354497627
LOG_CHANNEL_ID = 1365709885693493318
ADMIN_ROLE_ID = 1364134027585523772

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

LANG_INTRO_OUTRO = {
    "fr": {"intro": "# ``🏷️``__Voici la liste des tags__ :", "outro": "Prenez vos TAGS en https://discord.com/channels/1364133729114652742/1364149203764248656."},
    "en": {"intro": "# ``🏷️`` __Here are the available tags__ :", "outro": "Go on https://discord.com/channels/1364133729114652742/1367834060361175040 to get your TAGS."},
    "es": {"intro": "# ``🏷️`` __Aquí están las etiquetas disponibles__ :", "outro": " https://discord.com/channels/1364133729114652742/1367834342587498639 para obtener tus TAGS."}
}

TUTOS = {
    "fr": {
        "title": "📘 Tutoriel : Personnaliser ton tag",
        "description": (
            "# Bienvenue dans le tutoriel de personnalisation de ton profil !\n\n"
            "## **1. Accès au profil :**\n"
            "### Rends-toi dans la section dédiée à la personnalisation du serveur.\n\n"
            "## **2. Choix du tag :**\n"
            "### Choisis le tag qui te plaît dans la liste disponible.\n\n"
            "## **3. Activation :**\n"
            "### Ton tag sera automatiquement appliqué à ton profil.\n\n"
            "💡 *__Pense à mettre le tag <#1364264678062293142> dans ta bio pour le rendre visible partout !__*"
        ),
        "image": "https://cdn.discordapp.com/attachments/1364488298873225248/1364488520801980416/image.png"
    },
    "en": {
        "title": "📘 Tutorial: Customize Your Tag",
        "description": (
            "# Welcome to the tag customization tutorial!\n\n"
            "## **1. Access your profile:**\n"
            "### Go to the server’s customization section.\n\n"
            "## **2. Choose your tag:**\n"
            "### Pick your favorite tag from the available list.\n\n"
            "## **3. Activation:**\n"
            "### Your tag will be automatically applied to your profile.\n\n"
            "💡 *__Don't forget to add the tag <#1367834097120055349> in your bio to make it visible everywhere !__*"
        ),
        "image": "https://cdn.discordapp.com/attachments/1364488298873225248/1364488520801980416/image.png"
    },
    "es": {
        "title": "📘 Tutorial: Personaliza tu Tag",
        "description": (
            "# ¡Bienvenido al tutorial de personalización de tags!\n\n"
            "## **1. Accede a tu perfil:**\n"
            "### Ve a la sección de personalización del servidor.\n\n"
            "## **2. Elige tu tag:**\n"
            "### Selecciona tu tag favorito de la lista disponible.\n\n"
            "## **3. Activación:**\n"
            "### Tu tag se aplicará automáticamente a tu perfil.\n\n"
            "💡 *__No olvides poner el tag <#1367835092411748412> en tu biografía para que sea visible en todas partes.__*"
        ),
        "image": "https://cdn.discordapp.com/attachments/1364488298873225248/1364488520801980416/image.png"
    }
}

def is_admin():
    def predicate(interaction: discord.Interaction):
        return any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)
    return app_commands.check(predicate)

async def load_tags(channel: discord.TextChannel):
    async for message in channel.history(limit=100):
        try:
            data = json.loads(message.content)
            if isinstance(data, list):
                return data, message
        except json.JSONDecodeError:
            continue
    return [], None

async def save_tags(channel: discord.TextChannel, tags):
    _, old_msg = await load_tags(channel)
    content = json.dumps(tags, indent=2, ensure_ascii=False)
    if old_msg:
        await old_msg.edit(content=content)
    else:
        await channel.send(content)

async def log_action(bot, text):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(text)

@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Connecté en tant que {bot.user}")

@bot.tree.command(name="tag", description="Afficher un tag", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="Nom du tag à afficher")
async def tag(interaction: discord.Interaction, name: str):
    channel = bot.get_channel(TAG_CHANNEL_ID)
    tags, _ = await load_tags(channel)
    for tag in tags:
        if tag["name"].lower() == name.lower():
            await interaction.response.send_message(f"{tag['emoji']} **{tag['name']}**\n{tag['link']}")
            return
    await interaction.response.send_message("❌ Tag introuvable.")

@bot.tree.command(name="tag-add", description="Ajouter un tag", guild=discord.Object(id=GUILD_ID))
@is_admin()
@app_commands.describe(emoji="Emoji", name="Nom du tag", link="Lien associé")
async def tag_add(interaction: discord.Interaction, emoji: str, name: str, link: str):
    channel = bot.get_channel(TAG_CHANNEL_ID)
    tags, _ = await load_tags(channel)
    if any(t["name"].lower() == name.lower() for t in tags):
        await interaction.response.send_message("❌ Un tag avec ce nom existe déjà.")
        return
    tags.append({"emoji": emoji, "name": name, "link": link})
    await save_tags(channel, tags)
    await log_action(bot, f"🟢 Tag ajouté : {emoji} {name} - {link}")
    await interaction.response.send_message("✅ Tag ajouté.")

@bot.tree.command(name="tag-edit", description="Modifier un tag", guild=discord.Object(id=GUILD_ID))
@is_admin()
@app_commands.describe(name="Nom du tag à modifier", new_emoji="Nouvel emoji", new_name="Nouveau nom", new_link="Nouveau lien")
async def tag_edit(interaction: discord.Interaction, name: str, new_emoji: str = None, new_name: str = None, new_link: str = None):
    channel = bot.get_channel(TAG_CHANNEL_ID)
    tags, _ = await load_tags(channel)
    for tag in tags:
        if tag["name"].lower() == name.lower():
            if new_emoji: tag["emoji"] = new_emoji
            if new_name: tag["name"] = new_name
            if new_link: tag["link"] = new_link
            await save_tags(channel, tags)
            await log_action(bot, f"🟡 Tag modifié : {name}")
            await interaction.response.send_message("✅ Tag modifié.")
            return
    await interaction.response.send_message("❌ Tag introuvable.")

@bot.tree.command(name="remove-tag", description="Supprimer un tag", guild=discord.Object(id=GUILD_ID))
@is_admin()
@app_commands.describe(name="Nom du tag à supprimer")
async def remove_tag(interaction: discord.Interaction, name: str):
    channel = bot.get_channel(TAG_CHANNEL_ID)
    tags, _ = await load_tags(channel)
    new_tags = [t for t in tags if t["name"].lower() != name.lower()]
    if len(tags) == len(new_tags):
        await interaction.response.send_message("❌ Tag introuvable.")
        return
    await save_tags(channel, new_tags)
    await log_action(bot, f"🔴 Tag supprimé : {name}")
    await interaction.response.send_message("✅ Tag supprimé.")

@bot.tree.command(name="news-msg", description="Envoyer la liste des tags", guild=discord.Object(id=GUILD_ID))
@is_admin()
@app_commands.describe(lang="Langue (fr, en, es)")
async def news_msg(interaction: discord.Interaction, lang: str):
    lang = lang.lower()
    if lang not in LANG_INTRO_OUTRO:
        await interaction.response.send_message("❌ Langue invalide.")
        return
    intro = LANG_INTRO_OUTRO[lang]["intro"]
    outro = LANG_INTRO_OUTRO[lang]["outro"]
    channel = bot.get_channel(TAG_CHANNEL_ID)
    tags, _ = await load_tags(channel)
    body = "\n".join([f"{t['emoji']} **{t['name']}**" for t in tags])
    await interaction.response.send_message(f"{intro}\n\n{body}\n\n{outro}")

@bot.tree.command(name="tuto-fr", description="Tutoriel en français", guild=discord.Object(id=GUILD_ID))
async def tuto_fr(interaction: discord.Interaction):
    await send_tuto(interaction, "fr")


@bot.tree.command(name="tuto-en", description="Tutorial in English", guild=discord.Object(id=GUILD_ID))
async def tuto_en(interaction: discord.Interaction):
    await send_tuto(interaction, "en")


@bot.tree.command(name="tuto-es", description="Tutorial en español", guild=discord.Object(id=GUILD_ID))
async def tuto_es(interaction: discord.Interaction):
    await send_tuto(interaction, "es")


async def send_tuto(interaction: discord.Interaction, lang: str):
    tuto_data = TUTOS.get(lang, TUTOS["fr"])

    embed = discord.Embed(
        title=tuto_data["title"],
        description=tuto_data["description"],
        color=discord.Color.blue()
    )
    embed.set_image(url=tuto_data["image"])

    await interaction.response.send_message(embed=embed, ephemeral=False)

bot.run(os.getenv("DISCORD_TOKEN"))
