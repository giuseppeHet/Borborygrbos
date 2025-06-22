
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carica variabili da .env (da togliere se non lo usiamo)
# load_dotenv()

app = Flask(__name__)

# Upload config
UPLOAD_FOLDER = os.path.join('static', 'images', 'decks')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database config 
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://mtg_db_yzhn_user:d7byad1T8ssN5Fc5iaJnLVQup1q5yc7z@dpg-d14mouh5pdvs73fbmuk0-a/mtg_db_yzhn"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_year(date_str):
    try:
        if len(date_str) == 4:
            return date_str
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y")
    except:
        return "Sconosciuto"


class Player(db.Model):
    __tablename__ = 'players'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(255))

    decks = db.relationship('Deck', backref='player', lazy=True)
    matches_won = db.relationship('Match', backref='winner', lazy=True)
    match_participations = db.relationship('MatchPlayer', backref='player', lazy=True)


class Deck(db.Model):
    __tablename__ = 'decks'
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    colors = db.Column(db.String(100))
    image = db.Column(db.String(255))

    participations = db.relationship('MatchPlayer', backref='deck', lazy=True)


class Match(db.Model):
    __tablename__ = 'matches'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20))
    winner_id = db.Column(db.Integer, db.ForeignKey('players.id'))

    participants = db.relationship('MatchPlayer', backref='match', lazy=True)


class MatchPlayer(db.Model):
    __tablename__ = 'match_players'
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    deck_id = db.Column(db.Integer, db.ForeignKey('decks.id'), nullable=False)

# Inizializzazione del DB (una tantum, da commentare dopo primo avvio):
  with app.app_context():
    db.create_all()


# routes

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/players')
def players():
    return render_template('players.html')

@app.route('/players/list')
def players_list():
    players = Player.query.all()
    return render_template('players_list.html', players=players)

@app.route('/players/add', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        name = request.form['name']
        image = request.form.get('image') or 'default_player.jpg'
        new_player = Player(name=name, image=image)
        db.session.add(new_player)
        db.session.commit()
        return redirect(url_for('add_player', success=1))
    return render_template('add_player.html')

@app.route('/players/stats')
def player_stats():
    # Mappa ID → Nome
    players = Player.query.with_entities(Player.id, Player.name).all()
    player_names = {p.id: p.name for p in players}

    # Partite giocate
    played_counts = (
        db.session.query(MatchPlayer.player_id, db.func.count().label("total"))
        .group_by(MatchPlayer.player_id)
        .all()
    )
    most_played = sorted(
        [{'id': pid, 'name': player_names.get(pid, 'Sconosciuto'), 'matches_played': total}
         for pid, total in played_counts],
        key=lambda x: x['matches_played'], reverse=True
    )

    # Vittorie
    win_counts = (
        db.session.query(Match.winner_id.label("player_id"), db.func.count().label("total"))
        .filter(Match.winner_id.isnot(None))
        .group_by(Match.winner_id)
        .all()
    )
    most_wins = sorted(
        [{'id': row.player_id, 'name': player_names.get(row.player_id, 'Sconosciuto'), 'wins': row.total}
         for row in win_counts if row.player_id in player_names],
        key=lambda x: x['wins'], reverse=True
    )

    # Partite per anno
    matches_per_year = {name: {} for name in player_names.values()}
    match_rows = (
        db.session.query(MatchPlayer.player_id, Match.date)
        .join(Match, MatchPlayer.match_id == Match.id)
        .all()
    )
    for row in match_rows:
        try:
            year = int(row.date[:4])
        except:
            continue
        name = player_names.get(row.player_id)
        if name:
            matches_per_year[name][year] = matches_per_year[name].get(year, 0) + 1

    # Vittorie per anno
    wins_per_year = {name: {} for name in player_names.values()}
    win_rows = (
        db.session.query(Match.winner_id, Match.date)
        .filter(Match.winner_id.isnot(None))
        .all()
    )
    for row in win_rows:
        try:
            year = int(row.date[:4])
        except:
            continue
        name = player_names.get(row.winner_id)
        if name:
            wins_per_year[name][year] = wins_per_year[name].get(year, 0) + 1

    # Tutti gli anni unici
    matches_per_year_all_years = sorted({year for stats in matches_per_year.values() for year in stats})
    wins_per_year_all_years = sorted({year for stats in wins_per_year.values() for year in stats})

    return render_template('player_stats.html',
                           most_played=most_played,
                           most_wins=most_wins,
                           matches_per_year=matches_per_year,
                           wins_per_year=wins_per_year,
                           matches_per_year_all_years=matches_per_year_all_years,
                           wins_per_year_all_years=wins_per_year_all_years)


@app.route('/players/<int:player_id>')
def player_detail(player_id):
    player = Player.query.get_or_404(player_id)
    decks = Deck.query.filter_by(player_id=player_id).all()
    color_counter = {}

    # Elabora solo i colori (senza cambiare il tipo degli oggetti)
    for deck in decks:
        color_list = [c.strip() for c in (deck.colors or '').split(',') if c.strip()]
        sorted_colors = ','.join(sorted(color_list))
        deck.colors = sorted_colors  # aggiorna direttamente il campo dell'oggetto!
        for c_ in color_list:
            color_counter[c_] = color_counter.get(c_, 0) + 1

    total_decks = len(decks)
    total_matches = MatchPlayer.query.filter_by(player_id=player_id).count()
    total_wins = Match.query.filter_by(winner_id=player_id).count()
    total_losses = total_matches - total_wins

    # Mazzo più usato
    most_used_deck = (
        db.session.query(Deck.name, db.func.count().label("usage"))
        .join(MatchPlayer, Deck.id == MatchPlayer.deck_id)
        .filter(MatchPlayer.player_id == player_id)
        .group_by(Deck.id)
        .order_by(db.desc("usage"))
        .first()
    )

    # Mazzo con più vittorie
    most_successful_deck = (
        db.session.query(Deck.name, db.func.count().label("wins"))
        .join(MatchPlayer, Deck.id == MatchPlayer.deck_id)
        .join(Match, Match.id == MatchPlayer.match_id)
        .filter(Match.winner_id == player_id, MatchPlayer.player_id == player_id)
        .group_by(Deck.id)
        .order_by(db.desc("wins"))
        .first()
    )

    max_freq = max(color_counter.values(), default=0)
    favorite_colors = [c for c, v in color_counter.items() if v == max_freq]

    stats = {
        'total_decks': total_decks,
        'total_matches': total_matches,
        'total_wins': total_wins,
        'total_losses': total_losses,
        'most_used_deck': most_used_deck.name if most_used_deck else None,
        'most_successful_deck': most_successful_deck.name if most_successful_deck else None,
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

        if image and image.filename and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(save_path)

        new_deck = Deck(player_id=player_id, name=name, colors=colors, image=filename)
        db.session.add(new_deck)
        db.session.commit()

        return redirect(url_for('player_detail', player_id=player_id))

    return render_template('add_deck.html', player_id=player_id)

@app.route('/decks/<int:deck_id>/delete', methods=['POST'])
def delete_deck(deck_id):
    deck = Deck.query.get_or_404(deck_id)
    player_id = deck.player_id  
    #MatchPlayer.query.filter_by(deck_id=deck_id).delete()
    db.session.delete(deck)
    db.session.commit()
    return redirect(url_for('player_detail', player_id=player_id))

@app.route('/decks/<int:deck_id>/edit', methods=['POST'])
def edit_deck(deck_id):
    deck = Deck.query.get_or_404(deck_id)
    name = request.form.get('name', deck.name)
    colors = request.form.get('colors', deck.colors)
    image = request.files.get('image')
    
    # Aggiorna nome e colori
    deck.name = name
    deck.colors = colors

    # Se caricato, aggiorna l'immagine
    if image and image.filename and allowed_file(image.filename):
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        deck.image = filename

    db.session.commit()
    return redirect(url_for('player_detail', player_id=deck.player_id))

@app.route('/matches/list')
def match_list():
    matches = (
        db.session.query(Match)
        .outerjoin(Player, Match.winner_id == Player.id)
        .order_by(Match.id.desc())
        .all()
    )

    matches_by_year = defaultdict(list)

    for match in matches:
        match_dict = {
            'id': match.id,
            'date': match.date,
            'winner_id': match.winner_id,
            'winner_name': match.winner.name if match.winner else "Nessuno"
        }

        participants = (
            db.session.query(Player.name.label('player_name'),
                             Deck.name.label('deck_name'),
                             Deck.id.label('deck_id'))
            .join(MatchPlayer, Player.id == MatchPlayer.player_id)
            .join(Deck, Deck.id == MatchPlayer.deck_id)
            .filter(MatchPlayer.match_id == match.id)
            .all()
        )
        match_dict['participants'] = [dict(p._asdict()) for p in participants]

        winning_deck = (
            db.session.query(Deck.name, Deck.image)
            .join(MatchPlayer, Deck.id == MatchPlayer.deck_id)
            .filter(MatchPlayer.match_id == match.id, MatchPlayer.player_id == match.winner_id)
            .first()
        )
        match_dict['winning_deck'] = dict(name=winning_deck.name, image=winning_deck.image) if winning_deck else None

        try:
            year = int(match.date[:4]) if len(match.date) == 4 else datetime.strptime(match.date, "%Y-%m-%d").year
        except:
            year = "Sconosciuto"

        match_dict['year'] = year
        matches_by_year[year].append(match_dict)

    return render_template('match_list.html', matches_by_year=matches_by_year)

@app.route('/matches/add', methods=['GET', 'POST'])
def add_match():
    players = Player.query.all()
    decks = Deck.query.all()

    if request.method == 'POST':
        num_players = int(request.form.get('num_players'))
        date = request.form.get('date')
        winner_id = int(request.form.get('winner'))

        new_match = Match(date=date, winner_id=winner_id)
        db.session.add(new_match)
        db.session.flush()  # otteniamo match.id senza ancora commit

        for i in range(num_players):
            player_id = int(request.form.get(f'player_{i}'))
            deck_id = int(request.form.get(f'deck_{i}'))
            mp = MatchPlayer(match_id=new_match.id, player_id=player_id, deck_id=deck_id)
            db.session.add(mp)

        db.session.commit()
        return redirect(url_for('match_list'))

    return render_template('add_match.html', players=players, decks=decks)

@app.route('/matches/delete/<int:match_id>', methods=['POST'])
def delete_match(match_id):
    MatchPlayer.query.filter_by(match_id=match_id).delete()
    Match.query.filter_by(id=match_id).delete()
    db.session.commit()
    return redirect(url_for('match_list'))

@app.route('/matches/stats')
def match_stats():
    # Numero partite per anno
    matches_per_year = (
        db.session.query(
            db.case([
                (db.func.length(Match.date) == 4, Match.date),
            ], else_=db.func.substr(Match.date, 1, 4)).label("year"),
            db.func.count().label("total")
        )
        .group_by("year")
        .order_by("year DESC")
        .all()
    )

    # Giocatore più vincente
    top_winner = (
        db.session.query(Player.name, db.func.count().label("wins"))
        .join(Match, Match.winner_id == Player.id)
        .group_by(Player.id)
        .order_by(db.desc("wins"))
        .first()
    )

    # Mazzo più vincente
    top_deck = (
        db.session.query(Deck.name, db.func.count().label("wins"))
        .join(MatchPlayer, Deck.id == MatchPlayer.deck_id)
        .join(Match, Match.id == MatchPlayer.match_id)
        .filter(MatchPlayer.player_id == Match.winner_id)
        .group_by(Deck.id)
        .order_by(db.desc("wins"))
        .first()
    )

    # Giocatore con più sconfitte
    subq_wins = (
        db.session.query(Match.winner_id.label("winner_id"), db.func.count().label("w"))
        .group_by(Match.winner_id)
        .subquery()
    )
    most_losses = (
        db.session.query(
            Player.name,
            (db.func.count(MatchPlayer.id) - db.func.coalesce(subq_wins.c.w, 0)).label("losses")
        )
        .outerjoin(MatchPlayer, Player.id == MatchPlayer.player_id)
        .outerjoin(subq_wins, subq_wins.c.winner_id == Player.id)
        .group_by(Player.id, subq_wins.c.w)
        .order_by(db.desc("losses"))
        .first()
    )

    # Mazzo più perdente
    most_losing_deck = (
        db.session.query(Deck.name, db.func.count().label("losses"))
        .join(MatchPlayer, Deck.id == MatchPlayer.deck_id)
        .join(Match, Match.id == MatchPlayer.match_id)
        .filter(MatchPlayer.player_id != Match.winner_id)
        .group_by(Deck.id)
        .order_by(db.desc("losses"))
        .first()
    )

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
        "Ninjutsu = Intrufolare",
        "Cimitero = Discarica"
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
    app.run(debug=True)

