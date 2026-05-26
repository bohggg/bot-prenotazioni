import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

DB_PATH = "prenotazioni.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS prenotazioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            data TEXT NOT NULL,
            ora_inizio TEXT NOT NULL,
            ora_fine TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizzati {len(synced)} comandi.")
    except Exception as e:
        print(e)
    print(f"Bot online come {bot.user}")

@bot.tree.command(name="prenota", description="Crea una prenotazione (max 2 ore)")
@app_commands.describe(data="GG/MM/AAAA", dalle="HH:MM", alle="HH:MM", note="opzionale")
async def prenota(interaction: discord.Interaction, data: str, dalle: str, alle: str, note: str = None):
    try:
        data_obj = datetime.strptime(data, "%d/%m/%Y")
        inizio_obj = datetime.strptime(dalle, "%H:%M")
        fine_obj = datetime.strptime(alle, "%H:%M")
    except ValueError:
        await interaction.response.send_message("❌ Usa GG/MM/AAAA e HH:MM", ephemeral=True)
        return
    if data_obj.date() < datetime.now().date():
        await interaction.response.send_message("❌ Data nel passato", ephemeral=True)
        return
    if fine_obj <= inizio_obj:
        await interaction.response.send_message("❌ Fine prima di inizio", ephemeral=True)
        return
    durata = datetime.combine(datetime.min, fine_obj.time()) - datetime.combine(datetime.min, inizio_obj.time())
    if durata > timedelta(hours=2):
        await interaction.response.send_message("❌ Max 2 ore", ephemeral=True)
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ora_inizio, ora_fine FROM prenotazioni WHERE data = ?", (data,))
    for oi, of in c.fetchall():
        ei = datetime.strptime(oi, "%H:%M"); ef = datetime.strptime(of, "%H:%M")
        if inizio_obj < ef and fine_obj > ei:
            conn.close()
            await interaction.response.send_message(f"⚠️ Occupato dalle {oi} alle {of}", ephemeral=True)
            return
    c.execute("INSERT INTO prenotazioni VALUES (NULL,?,?,?,?,?,?,?)",
              (str(interaction.user.id), interaction.user.display_name, data, dalle, alle, note, datetime.now().isoformat()))
    pren_id = c.lastrowid
    conn.commit(); conn.close()
    embed = discord.Embed(title="✅ Prenotazione", color=0x00ff88)
    embed.add_field(name="ID", value=f"#{pren_id}")
    embed.add_field(name="Data", value=data)
    embed.add_field(name="Orario", value=f"{dalle}-{alle}")
    if note: embed.add_field(name="Note", value=note)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="prenotazioni", description="Vedi le tue")
async def prenotazioni(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT id,data,ora_inizio,ora_fine,note FROM prenotazioni WHERE user_id=?", (str(interaction.user.id),))
    rows = c.fetchall(); conn.close()
    if not rows: await interaction.response.send_message("Nessuna", ephemeral=True); return
    embed = discord.Embed(title="📅 Tue prenotazioni")
    for i,d,oi,of,n in rows: embed.add_field(name=f"#{i}", value=f"{d} {oi}-{of} {n or ''}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="cancella", description="Cancella")
async def cancella(interaction: discord.Interaction, id_prenotazione: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("DELETE FROM prenotazioni WHERE id=? AND user_id=?", (id_prenotazione, str(interaction.user.id)))
    conn.commit(); conn.close()
    await interaction.response.send_message("✅ Cancellata", ephemeral=True)

bot.run(TOKEN)
