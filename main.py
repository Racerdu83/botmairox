import discord
from discord.ext import commands
from discord import app_commands
import json
import os

GUILD_ID = 1364133729114652742  # Remplace par ton ID de serveur
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
        "title": "📘 Tutoriel : Personnaliser ton Profils",
        "description": (
            " Voici comment personnaliser ton profil et sélectionner un tag. Suis les étapes ci-dessous pour activer ton tag partout ! !\n\n"
            "## **Etape 1 :**\n"
            "### Rejoins le serveur et accède à la section de personnalisation de ton profil.\n\n"
            "## **Etape 2 :**\n"
            "### Sélectionne le tag que tu souhaites dans la liste des options disponibles..\n\n"
            "## **Etape 3 :**\n"
            "### Une fois sélectionné, ton tag sera activé partout.\n\n"
            "💡 *__Pense à mettre le tag dans <#1364264678062293142> !__*"
        ),
        "image": "https://cdn.discordapp.com/attachments/1364488298873225248/1364488520801980416/image.png"
    },
    "en": {
        "title": "📘 Tutorial: Customize Your Profils",
        "description": (
            " Here's how to personalize your profile and select a tag. Follow the steps below to activate your tag everywhere !\n\n"
            "## **Stage 1 :**\n"
            "### Join the server and access the personalization section of your profile.\n\n"
            "## **Stage 2 :**\n"
            "### Select the tag you want from the list of available options..\n\n"
            "## **Stage 3 ::**\n"
            "### Once selected, your tag will be activated everywhere.\n\n"
            "💡 *__Don't forget to add the tag <#1367834097120055349> !__*"
        ),
        "image": "https://cdn.discordapp.com/attachments/1364488298873225248/1364488520801980416/image.png"
    },
    "es": {
        "title": "📘 Tutorial: Personaliza tu Perfiles",
        "description": (
            "# ¡Aquí se explica cómo personalizar su perfil y seleccionar una etiqueta. ¡Sigue los pasos a continuación para activar tu etiqueta en todas partes!\n\n"
            "## **Paso 1**\n"
            "### Únete al servidor y accede a la sección de personalización de tu perfil.\n\n"
            "## **Paso 2**\n"
            "### Seleccione la etiqueta que desee de la lista de opciones disponibles.\n\n"
            "## **Paso 3**\n"
            "### Una vez seleccionada, su etiqueta se activará en todas partes.\n\n"
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
    tags = []
    async for message in channel.history(limit=200):
        if message.author == channel.guild.me and message.content.startswith('{'):
            try:
                data = json.loads(message.content)
                if isinstance(data, dict) and all(k in data for k in ("name", "emoji", "link")):
                    data["__msg__"] = message  # Associe le message à l'objet tag
                    tags.append(data)
            except json.JSONDecodeError:
                continue
    return tags
async def delete_tag(channel: discord.TextChannel, name: str):
    tags = await load_tags(channel)
    for tag in tags:
        if tag["name"].lower() == name.lower():
            await tag["__msg__"].delete()
            return True
    return False

async def log_action(bot, text):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(text)
async def update_news_msg(channel: discord.TextChannel):
    # Charger tous les tags
    tags = await load_tags(channel)

    # Construire le message
    body = "\n".join([f"## {t['emoji']} **{t['name']}**\n{t['link']}" for t in tags])

    # Rechercher un message existant avec les tags
    news_msg = None
    async for message in channel.history(limit=200):
        if message.author == channel.guild.me and message.content.startswith("# ``🏷️``"):
            news_msg = message
            break

    # Si un message existe, on le réédite
    if news_msg:
        try:
            await news_msg.edit(content=f"{LANG_INTRO_OUTRO['fr']['intro']}\n\n{body}\n\n{LANG_INTRO_OUTRO['fr']['outro']}")
        except Exception as e:
            print(f"Erreur lors de la mise à jour du message des tags : {e}")
    # Si aucun message n'existe, on crée un nouveau message
    else:
        try:
            await channel.send(f"{LANG_INTRO_OUTRO['fr']['intro']}\n\n{body}\n\n{LANG_INTRO_OUTRO['fr']['outro']}")
        except Exception as e:
            print(f"Erreur lors de l'envoi du message des tags : {e}")
@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Connecté en tant que {bot.user}")

@bot.tree.command(name="tags", description="Afficher un tag", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="Nom du tag à afficher")
@app_commands.checks.has_role(1364134027585523772)
async def tag(interaction: discord.Interaction, name: str):
    channel = bot.get_channel(TAG_CHANNEL_ID)
    tags = await load_tags(channel)

    # Recherche insensible à la casse
    found_tag = None
    for tag in tags:
        if tag["name"].lower() == name.lower():  # Comparaison insensible à la casse
            found_tag = tag
            break

    if found_tag:
        await interaction.response.send_message(f"{found_tag['emoji']} **{found_tag['name']}**\n{found_tag['link']}")
    else:
        await interaction.response.send_message("❌ Tag introuvable.")
@bot.tree.command(name="tag-add", description="Ajouter un tag", guild=discord.Object(id=GUILD_ID))
@is_admin()
@app_commands.describe(emoji="Emoji", name="Nom du tag", link="Lien associé")
async def tag_add(interaction: discord.Interaction, emoji: str, name: str, link: str):
            try:
                # Récupérer le canal des tags
                channel = bot.get_channel(TAG_CHANNEL_ID)
                if not channel:
                    await interaction.response.send_message("❌ Le canal spécifié est introuvable.")
                    return

                # Charger les tags existants
                tags = await load_tags(channel)

                # Vérifier si un tag avec ce nom existe déjà
                existing_tag = next((t for t in tags if t["name"].lower() == name.lower()), None)
                if existing_tag:
                    await interaction.response.send_message(f"❌ Un tag avec le nom '{name}' existe déjà.")
                    return

                # Créer un nouveau tag
                new_tag = {"emoji": emoji, "name": name, "link": link}

                # Sauvegarder ce nouveau tag dans la liste des tags
                await save_tag(channel, new_tag)  # Sauvegarde du tag

                # Mettre à jour le message contenant la liste des tags
                await update_news_msg(channel)

                # Log de l'ajout du tag
                await log_action(bot, f"🟢 Tag ajouté : {emoji} {name} - {link}")

                # Envoyer une réponse de succès
                await interaction.response.send_message(f"✅ Tag ajouté : {emoji} {name} - {link}")
            except Exception as e:
                await interaction.response.send_message(f"❌ Une erreur est survenue lors de l'ajout du tag : {str(e)}")
                print(f"Erreur dans la commande /tag-add: {e}")
@bot.tree.command(name="tag-edit", description="Modifier un tag", guild=discord.Object(id=GUILD_ID))
@is_admin()
@app_commands.describe(name="Nom du tag à modifier", new_emoji="Nouvel emoji", new_name="Nouveau nom", new_link="Nouveau lien")
async def tag_edit(interaction: discord.Interaction, name: str, new_emoji: str = None, new_name: str = None, new_link: str = None):
    channel = bot.get_channel(TAG_CHANNEL_ID)
    tags = await load_tags(channel)
    for tag in tags:
        if tag["name"].lower() == name.lower():
            if new_emoji: tag["emoji"] = new_emoji
            if new_name: tag["name"] = new_name
            if new_link: tag["link"] = new_link

            # Sauvegarder le tag modifié
            await save_tag(channel, tag)  # Sauvegarder le seul tag modifié

            # Log de la modification
            await log_action(bot, f"🟡 Tag modifié : {name}")

            await interaction.response.send_message(f"✅ Tag modifié : {tag['name']}")

            # Recharger la liste des tags après modification
            await load_tags(channel)

            return

    await interaction.response.send_message("❌ Tag introuvable.")


@bot.tree.command(name="remove-tag", description="Supprimer un tag", guild=discord.Object(id=GUILD_ID))
@is_admin()
@app_commands.describe(name="Nom du tag à supprimer")
async def remove_tag(interaction: discord.Interaction, name: str):
    channel = bot.get_channel(TAG_CHANNEL_ID)
    tags = await load_tags(channel)
    new_tags = [t for t in tags if t["name"].lower() != name.lower()]
    if len(tags) == len(new_tags):
        await interaction.response.send_message("❌ Tag introuvable.")
        return

    # Supprimer le tag
    deleted = await delete_tag(channel, name)
    if deleted:
        await log_action(bot, f"🔴 Tag supprimé : {name}")
        await interaction.response.send_message("✅ Tag supprimé.")
    else:
        await interaction.response.send_message("❌ Tag introuvable.")

    # Recharger la liste des tags après suppression
    await load_tags(channel)
@bot.tree.command(name="news-msg", description="Envoyer un message de news avec les tags", guild=discord.Object(id=GUILD_ID))
@is_admin()
@app_commands.describe(lang="Langue (fr, en, es)")
async def news_msg(interaction: discord.Interaction, lang: str):
                                        try:
                                            # Vérifier la langue
                                            lang = lang.lower()
                                            if lang not in LANG_INTRO_OUTRO:
                                                await interaction.response.send_message("❌ Langue invalide.", ephemeral=True)
                                                return

                                            # Obtenir l'intro et l'outro en fonction de la langue
                                            intro = LANG_INTRO_OUTRO[lang]["intro"]
                                            outro = LANG_INTRO_OUTRO[lang]["outro"]

                                            # Charger les tags disponibles
                                            channel = bot.get_channel(TAG_CHANNEL_ID)
                                            tags = await load_tags(channel)

                                            # Créer le contenu du message avec tous les tags, ajoutant "##" pour agrandir les noms des tags
                                            body = "\n".join([f"## {tag['emoji']} **{tag['name']}**" for tag in tags])

                                            # Construire le message final
                                            total_content = f"{intro}\n\n{body}\n\n{outro}"

                                            # Diviser le message en morceaux de 2000 caractères maximum
                                            max_length = 2000  # Limite de Discord par message
                                            parts = []
                                            while len(total_content) > max_length:
                                                # On trouve la dernière coupe possible sans couper un tag en deux
                                                cut_point = total_content.rfind("\n", 0, max_length)
                                                parts.append(total_content[:cut_point])
                                                total_content = total_content[cut_point:].lstrip("\n")  # On retire le premier "\n" pour ne pas le dupliquer
                                            parts.append(total_content)  # Ajouter le reste du message

                                            # Envoyer chaque morceau en toute sécurité
                                            for part in parts:
                                                await interaction.channel.send(part)

                                            await interaction.response.send_message("✅ Message envoyé en plusieurs parties.")

                                        except Exception as e:
                                            await interaction.response.send_message(f"❌ Une erreur est survenue : {str(e)}")
                                            print(f"Erreur dans la commande /news-msg: {e}")
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
