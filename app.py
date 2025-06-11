from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import random
from sqlalchemy import func

app = Flask(__name__)

# Config
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3').replace("postgres://", "postgresql://")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = os.path.join('static', 'images', 'decks')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# Helpers
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Models
class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    image = db.Column(db.String(255), nullable=True)
    decks = relationship('Deck', backref='player', cascade="all, delete-orphan")
    wins = relationship('Match', backref='winner', foreign_keys='Match.winner_id')

class Deck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    colors = db.Column(db.String(120), nullable=True)
    image = db.Column(db.String(255), nullable=True)
    match_players = relationship('MatchPlayer', backref='deck', cascade="all, delete-orphan")
 
    
class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=True)
    winner_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=True)
    match_players = relationship('MatchPlayer', backref='match', cascade="all, delete-orphan")

class MatchPlayer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    deck_id = db.Column(db.Integer, db.ForeignKey('deck.id'), nullable=False)

    player = relationship('Player')  

# Routes
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
        player = Player(name=name, image=image)
        db.session.add(player)
        db.session.commit()
        return redirect(url_for('add_player', success=1))
    return render_template('add_player.html')


# Rotte per partite
@app.route('/matches')
def matches():
    return render_template('matches.html')

@app.route('/matches/list')
def match_list():
    matches = Match.query.order_by(Match.id.desc()).all()
    matches_by_year = defaultdict(list)

    for match in matches:
        match_dict = {
            'id': match.id,
            'date': match.date,
            'winner_id': match.winner_id,
            'winner_name': match.winner.name if match.winner else None,
            'participants': [
                {
                    'player_name': p.player.name,
                    'deck_name': p.deck.name,
                    'deck_id': p.deck.id
                } for p in match.match_players
            ],
            'winning_deck': next(({
                'name': p.deck.name,
                'image': p.deck.image
            } for p in match.match_players if p.player_id == match.winner_id), None)
        }

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

        match = Match(winner_id=winner_id, date=date)
        db.session.add(match)
        db.session.commit()

        for i in range(num_players):
            player_id = int(request.form.get(f'player_{i}'))
            deck_id = int(request.form.get(f'deck_{i}'))
            match_player = MatchPlayer(match_id=match.id, player_id=player_id, deck_id=deck_id)
            db.session.add(match_player)

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
    matches_per_year = db.session.query(
        func.coalesce(func.substr(Match.date, 1, 4), 'Sconosciuto').label("year"),
        func.count(Match.id)
    ).group_by("year").order_by("year desc").all()

    top_winner = db.session.query(
        Player.name, func.count(Match.id).label("wins")
    ).join(Match, Match.winner_id == Player.id).group_by(Player.id).order_by(func.count(Match.id).desc()).first()

    top_deck = db.session.query(
        Deck.name, func.count(MatchPlayer.id)
    ).join(MatchPlayer, Deck.id == MatchPlayer.deck_id
    ).join(Match, MatchPlayer.match_id == Match.id
    ).filter(MatchPlayer.player_id == Match.winner_id
    ).group_by(Deck.id).order_by(func.count(MatchPlayer.id).desc()).first()

    most_losses = db.session.query(
        Player.name, (func.count(MatchPlayer.id) - func.coalesce(func.count(Match.id), 0)).label("losses")
    ).join(MatchPlayer, Player.id == MatchPlayer.player_id
    ).outerjoin(Match, Match.winner_id == Player.id
    ).group_by(Player.id).order_by("losses desc").first()

    most_losing_deck = db.session.query(
        Deck.name, func.count(MatchPlayer.id).label("losses")
    ).join(MatchPlayer, Deck.id == MatchPlayer.deck_id
    ).join(Match, Match.id == MatchPlayer.match_id
    ).filter(MatchPlayer.player_id != Match.winner_id
    ).group_by(Deck.id).order_by("losses desc").first()

    return render_template('match_stats.html',
                           matches_per_year=matches_per_year,
                           top_winner=top_winner,
                           top_deck=top_deck,
                           most_losses=most_losses,
                           most_losing_deck=most_losing_deck)

# Rotte extra
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

@app.route('/extra/random', methods=['GET', 'POST'])
def extra_random():
    tavoli = []
    names = []

    if request.method == 'POST':
        num_players = int(request.form.get('num_players'))
        num_tables = int(request.form.get('num_tables'))

        names = [request.form.get(f'name_{i}').strip() for i in range(num_players)]
        names = [name for name in names if name]
        random.shuffle(names)

        tavoli = [[] for _ in range(num_tables)]
        for i, name in enumerate(names):
            tavoli[i % num_tables].append(name)

    return render_template('extra_random.html', tavoli=tavoli)


if __name__ == '__main__':
    db.create_all()
    app.run()
