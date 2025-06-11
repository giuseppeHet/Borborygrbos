
from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.join('static', 'images', 'decks')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_year(date_str):
    try:
        if len(date_str) == 4:
            return date_str
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y")
    except:
        return "Sconosciuto"

def init_db():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()

    # Giocatori
    c.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            image TEXT
        )
    ''')

    # Mazzi
    c.execute('''
        CREATE TABLE IF NOT EXISTS decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            name TEXT NOT NULL,
            colors TEXT,
            image TEXT,
            FOREIGN KEY(player_id) REFERENCES players(id)
        )
    ''')

    # Partite (solo data e vincitore)
    c.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            winner_id INTEGER,
            FOREIGN KEY(winner_id) REFERENCES players(id)
        )
    ''')

    # Partecipanti a ogni partita
    c.execute('''
        CREATE TABLE IF NOT EXISTS match_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            deck_id INTEGER NOT NULL,
            FOREIGN KEY (match_id) REFERENCES matches(id),
            FOREIGN KEY (player_id) REFERENCES players(id),
            FOREIGN KEY (deck_id) REFERENCES decks(id)
        )
    ''')

    conn.commit()
    conn.close()


# routes

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/players')
def players():
    return render_template('players.html')

@app.route('/players/list')
def players_list():
    conn = sqlite3.connect('db.sqlite3')
    players = conn.execute('SELECT * FROM players').fetchall()
    conn.close()
    return render_template('players_list.html', players=players)

@app.route('/players/add', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        name = request.form['name']
        image = request.form.get('image') or 'default_player.jpg'
        conn = sqlite3.connect('db.sqlite3')
        conn.execute('INSERT INTO players (name, image) VALUES (?, ?)', (name, image))
        conn.commit()
        conn.close()
        # Reindirizza alla stessa pagina con parametro success=1
        return redirect(url_for('add_player', success=1))
    return render_template('add_player.html')

from collections import defaultdict
from datetime import datetime

'''
@app.route('/decks/<int:deck_id>/edit', methods=['GET', 'POST'])
def edit_deck(deck_id):
    conn = sqlite3.connect('db.sqlite3')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    deck = c.execute('SELECT * FROM decks WHERE id = ?', (deck_id,)).fetchone()
    if not deck:
        conn.close()
        return "Deck not found", 404

    if request.method == 'POST':
        name = request.form['name']
        colors = request.form['colors']
        image = request.files.get('image')

        filename = deck['image']  # default to existing image

        if image and image.filename and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            save_path = os.path.normpath(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image.save(save_path)

        c.execute('UPDATE decks SET name = ?, colors = ?, image = ? WHERE id = ?',
                  (name, colors, filename, deck_id))
        conn.commit()
        conn.close()
        return redirect(url_for('player_detail', player_id=deck['player_id']))

    conn.close()
    return render_template('edit_deck.html', deck=deck)
'''

@app.route('/players/stats')
def player_stats():
    conn = sqlite3.connect('db.sqlite3')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Tutti i giocatori
    players = c.execute('SELECT id, name FROM players').fetchall()
    player_names = {p['id']: p['name'] for p in players}

    # Conta partite giocate
    played_counts = c.execute('''
        SELECT player_id, COUNT(*) as total
        FROM match_players
        GROUP BY player_id
    ''').fetchall()

    most_played = sorted(
        [{'id': row['player_id'], 'name': player_names[row['player_id']], 'matches_played': row['total']}
         for row in played_counts],
        key=lambda x: x['matches_played'], reverse=True
    )

    # Conta vittorie
    win_counts = c.execute('''
        SELECT winner_id as player_id, COUNT(*) as total
        FROM matches
        WHERE winner_id IS NOT NULL
        GROUP BY winner_id
    ''').fetchall()

    most_wins = sorted(
        [{'id': row['player_id'], 'name': player_names[row['player_id']], 'wins': row['total']}
         for row in win_counts if row['player_id'] in player_names],
        key=lambda x: x['wins'], reverse=True
    )

    # Partite per anno per giocatore
    matches_per_year = {name: {} for name in player_names.values()}
    match_rows = c.execute('''
        SELECT mp.player_id, m.date
        FROM match_players mp
        JOIN matches m ON mp.match_id = m.id
    ''').fetchall()

    for row in match_rows:
        try:
            year = int(row['date'][:4])
        except:
            continue
        name = player_names.get(row['player_id'])
        if name:
            matches_per_year[name][year] = matches_per_year[name].get(year, 0) + 1

    # Vittorie per anno per giocatore
    wins_per_year = {name: {} for name in player_names.values()}
    win_rows = c.execute('''
        SELECT winner_id, date
        FROM matches
        WHERE winner_id IS NOT NULL
    ''').fetchall()

    for row in win_rows:
        try:
            year = int(row['date'][:4])
        except:
            continue
        name = player_names.get(row['winner_id'])
        if name:
            wins_per_year[name][year] = wins_per_year[name].get(year, 0) + 1

    # Estrai tutti gli anni unici ordinati
    matches_per_year_all_years = sorted({year for stats in matches_per_year.values() for year in stats})
    wins_per_year_all_years = sorted({year for stats in wins_per_year.values() for year in stats})

    conn.close()

    return render_template('player_stats.html',
                           most_played=most_played,
                           most_wins=most_wins,
                           matches_per_year=matches_per_year,
                           wins_per_year=wins_per_year,
                           matches_per_year_all_years=matches_per_year_all_years,
                           wins_per_year_all_years=wins_per_year_all_years)

@app.route('/players/<int:player_id>')
def player_detail(player_id):
    conn = sqlite3.connect('db.sqlite3')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Dati del giocatore
    player = c.execute('SELECT * FROM players WHERE id = ?', (player_id,)).fetchone()

    # Mazzi
    rows = c.execute('SELECT * FROM decks WHERE player_id = ?', (player_id,)).fetchall()
    decks = []
    color_counter = {}

    for row in rows:
        deck = dict(row)
        colors = deck.get('colors', '')
        if colors:
            color_list = [c.strip() for c in colors.split(',') if c.strip()]
            sorted_colors = ','.join(sorted(color_list))
            deck['colors'] = sorted_colors
            for c_ in color_list:
                color_counter[c_] = color_counter.get(c_, 0) + 1
        decks.append(deck)

    # Statistiche
    total_decks = len(decks)
    total_matches = c.execute('SELECT COUNT(*) FROM match_players WHERE player_id = ?', (player_id,)).fetchone()[0]
    total_wins = c.execute('SELECT COUNT(*) FROM matches WHERE winner_id = ?', (player_id,)).fetchone()[0]
    total_losses = total_matches - total_wins

    most_used_deck = c.execute('''
        SELECT d.name, COUNT(*) as usage
        FROM match_players mp
        JOIN decks d ON mp.deck_id = d.id
        WHERE mp.player_id = ?
        GROUP BY d.id
        ORDER BY usage DESC
        LIMIT 1
    ''', (player_id,)).fetchone()

    most_successful_deck = c.execute('''
        SELECT d.name, COUNT(*) as wins
        FROM matches m
        JOIN match_players mp ON m.id = mp.match_id AND m.winner_id = mp.player_id
        JOIN decks d ON mp.deck_id = d.id
        WHERE mp.player_id = ?
        GROUP BY d.id
        ORDER BY wins DESC
        LIMIT 1
    ''', (player_id,)).fetchone()

    max_freq = max(color_counter.values(), default=0)
    favorite_colors = [color for color, count in color_counter.items() if count == max_freq]

    conn.close()

    stats = {
        'total_decks': total_decks,
        'total_matches': total_matches,
        'total_wins': total_wins,
        'total_losses': total_losses,
        'most_used_deck': most_used_deck['name'] if most_used_deck else None,
        'most_successful_deck': most_successful_deck['name'] if most_successful_deck else None,
        'favorite_colors': favorite_colors
    }

    return render_template('player_detail.html', player=player, decks=decks, stats=stats)


@app.route('/players/<int:player_id>/add_deck', methods=['GET', 'POST'])
def add_deck(player_id):
    if request.method == 'POST':
        name = request.form['name']
        colors = request.form['colors']
        image = request.files.get('image')
        filename = None

        # Gestione immagine solo se presente e valida
        if image and image.filename and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            save_path = os.path.normpath(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image.save(save_path)

        # Salva i dati nel database
        conn = sqlite3.connect('db.sqlite3')
        conn.execute('INSERT INTO decks (player_id, name, colors, image) VALUES (?, ?, ?, ?)',
                     (player_id, name, colors, filename))
        conn.commit()
        conn.close()

        return redirect(url_for('player_detail', player_id=player_id))

    return render_template('add_deck.html', player_id=player_id)


@app.route('/matches')
def matches():
    return render_template('matches.html')

from collections import defaultdict
from datetime import datetime

from collections import defaultdict
from datetime import datetime

@app.route('/matches/list')
def match_list():
    conn = sqlite3.connect('db.sqlite3')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    matches = c.execute('''
        SELECT m.id, m.date, m.winner_id, pw.name as winner_name
        FROM matches m
        LEFT JOIN players pw ON m.winner_id = pw.id
        ORDER BY m.id DESC
    ''').fetchall()

    matches_by_year = defaultdict(list)

    for match in matches:
        match_dict = dict(match)

        # Partecipanti
        participants = c.execute('''
            SELECT p.name as player_name, d.name as deck_name, d.id as deck_id
            FROM match_players mp
            JOIN players p ON mp.player_id = p.id
            JOIN decks d ON mp.deck_id = d.id
            WHERE mp.match_id = ?
        ''', (match['id'],)).fetchall()
        match_dict['participants'] = [dict(p) for p in participants]

        # Mazzo vincente
        winning_deck = c.execute('''
            SELECT d.name, d.image
            FROM match_players mp
            JOIN decks d ON mp.deck_id = d.id
            WHERE mp.match_id = ? AND mp.player_id = ?
            LIMIT 1
        ''', (match['id'], match['winner_id'])).fetchone()
        match_dict['winning_deck'] = dict(winning_deck) if winning_deck else None

        # Estrai anno dalla data (che è nel formato YYYY o YYYY-MM-DD)
        try:
            # Se è solo un anno (es. "2023"), parsalo direttamente
            if len(match['date']) == 4:
                year = int(match['date'])
            else:
                year = datetime.strptime(match['date'], "%Y-%m-%d").year
        except:
            year = "Sconosciuto"

        match_dict['year'] = year  # Permette di accedere all’anno nel template

        matches_by_year[year].append(match_dict)

    conn.close()
    return render_template('match_list.html', matches_by_year=matches_by_year)


@app.route('/matches/add', methods=['GET', 'POST'])
def add_match():
    conn = sqlite3.connect('db.sqlite3')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    players = c.execute('SELECT * FROM players').fetchall()
    decks = c.execute('SELECT * FROM decks').fetchall()
    conn.close()

    # Converti da Row a dict per renderli serializzabili e utilizzabili nel template
    players = [dict(row) for row in players]
    decks = [dict(row) for row in decks]

    if request.method == 'POST':
        num_players = int(request.form.get('num_players'))
        date = request.form.get('date')
        winner_id = int(request.form.get('winner'))

        conn = sqlite3.connect('db.sqlite3')
        c = conn.cursor()

        # Inserisce la partita
        c.execute('INSERT INTO matches (winner_id, date) VALUES (?, ?)', (winner_id, date))
        match_id = c.lastrowid

        # Inserisce i partecipanti
        for i in range(num_players):
            player_id = int(request.form.get(f'player_{i}'))
            deck_id = int(request.form.get(f'deck_{i}'))
            c.execute('INSERT INTO match_players (match_id, player_id, deck_id) VALUES (?, ?, ?)',
                      (match_id, player_id, deck_id))

        conn.commit()
        conn.close()
        return redirect(url_for('match_list'))

    return render_template('add_match.html', players=players, decks=decks)

@app.route('/matches/delete/<int:match_id>', methods=['POST'])
def delete_match(match_id):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()

    # Cancella prima i partecipanti legati alla partita
    c.execute('DELETE FROM match_players WHERE match_id = ?', (match_id,))
    # Poi la partita stessa
    c.execute('DELETE FROM matches WHERE id = ?', (match_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('match_list'))

@app.route('/matches/stats')
def match_stats():
    conn = sqlite3.connect('db.sqlite3')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Numero partite per anno
    matches_per_year = c.execute('''
        SELECT 
            CASE 
                WHEN LENGTH(date) = 4 THEN date 
                ELSE strftime('%Y', date)
            END as year,
            COUNT(*) as total
        FROM matches
        GROUP BY year
        ORDER BY year DESC
    ''').fetchall()

    # Giocatore più vincente
    top_winner = c.execute('''
        SELECT p.name, COUNT(*) as wins
        FROM matches m
        JOIN players p ON m.winner_id = p.id
        GROUP BY m.winner_id
        ORDER BY wins DESC
        LIMIT 1
    ''').fetchone()

    # Mazzo più vincente (quello usato dal vincitore)
    top_deck = c.execute('''
        SELECT d.name, COUNT(*) as wins
        FROM match_players mp
        JOIN matches m ON mp.match_id = m.id
        JOIN decks d ON mp.deck_id = d.id
        WHERE mp.player_id = m.winner_id
        GROUP BY d.id
        ORDER BY wins DESC
        LIMIT 1
    ''').fetchone()

    # Giocatore più perdente (quello che ha partecipato a più partite ma ha vinto meno)
    most_losses = c.execute('''
        SELECT p.name, (COUNT(mp.id) - IFNULL(wins.w, 0)) as losses
        FROM players p
        LEFT JOIN match_players mp ON p.id = mp.player_id
        LEFT JOIN (
            SELECT winner_id, COUNT(*) as w FROM matches GROUP BY winner_id
        ) wins ON wins.winner_id = p.id
        GROUP BY p.id
        ORDER BY losses DESC
        LIMIT 1
    ''').fetchone()

    # Mazzo più perdente (quello più usato da chi non ha vinto)
    most_losing_deck = c.execute('''
        SELECT d.name, COUNT(*) as losses
        FROM match_players mp
        JOIN matches m ON mp.match_id = m.id
        JOIN decks d ON mp.deck_id = d.id
        WHERE mp.player_id != m.winner_id
        GROUP BY d.id
        ORDER BY losses DESC
        LIMIT 1
    ''').fetchone()

    conn.close()

    return render_template('match_stats.html',
                           matches_per_year=matches_per_year,
                           top_winner=top_winner,
                           top_deck=top_deck,
                           most_losses=most_losses,
                           most_losing_deck=most_losing_deck)


@app.route('/extra')
def extra():
    return render_template('extra.html')

@app.route('/extra/links')
def extra_links():
    links = [
        {"name": "Scryfall", "url": "https://scryfall.com/"},
        {"name": "EDHREC", "url": "https://edhrec.com/"},
        {"name": "MTG Print", "url": "https://mtgprint.net/"},
        {"name": "MTG Blacksmith", "url": "https://mtgcardsmith.com/mtg-token-maker/"},
        {"name": "EDH Power Level", "url": "https://edhpowerlevel.com/"}
    ]
    return render_template('extra_links.html', links=links)

@app.route('/extra/borb')
def borb():
    keywords = [
        "Antimalocchio = Scaccia malocchio",
        "Danni = Dolori",
        "Guadagnare punti vita = Curarsi",
        "Ninjutsu = Intrufolare"
    ]
    return render_template('borb.html', keywords=keywords)

import random
from flask import request, render_template

@app.route('/extra/random', methods=['GET', 'POST'])
def extra_random():
    tavoli = []
    names = []

    if request.method == 'POST':
        num_players = int(request.form.get('num_players'))
        num_tables = int(request.form.get('num_tables'))

        # Raccoglie i nomi
        names = [request.form.get(f'name_{i}').strip() for i in range(num_players)]
        names = [name for name in names if name]  # Rimuove vuoti
        random.shuffle(names)

        # Assegna ai tavoli
        tavoli = [[] for _ in range(num_tables)]
        for i, name in enumerate(names):
            tavoli[i % num_tables].append(name)

    return render_template('extra_random.html', tavoli=tavoli)


if __name__ == '__main__':
    #init_db()
    app.run()
