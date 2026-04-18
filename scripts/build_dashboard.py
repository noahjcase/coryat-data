#!/usr/bin/env python3
"""
Generate an HTML Jeopardy dashboard from game CSV files.
Reads from games/ directory and produces index.html.
"""

import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import json

GAMES_DIR = Path("games")
OUTPUT_FILE = Path("index.html")
ROLLING_WINDOW = 5


def parse_games():
    """Parse all game CSVs and return aggregated stats."""
    games = []
    game_scores = {}

    for csv_file in sorted(GAMES_DIR.glob("*.csv")):
        date_str = csv_file.stem
        clues = []

        with open(csv_file, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                clues.append(row)

        coryat = 0
        for clue in clues:
            value = int(clue["value"])
            result = clue["result"]
            if result in ("c", "dc"):
                coryat += value
            elif result in ("w", "dw"):
                coryat -= value

        game_scores[date_str] = coryat
        games.append({"date": date_str, "clues": clues, "coryat": coryat})

    return games, game_scores


def rolling_average(values, window):
    result = []
    for i, _ in enumerate(values):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        result.append(round(sum(chunk) / len(chunk), 1))
    return result


def calculate_stats(games, game_scores):
    """Calculate aggregate statistics."""
    if not games:
        return {}

    coryats = list(game_scores.values())
    correct_count = 0
    wrong_count = 0
    skipped_count = 0
    unrevealed_count = 0
    dd_correct = 0
    dd_wrong = 0
    value_accuracy = defaultdict(lambda: {"correct": 0, "total": 0})
    round_accuracy = defaultdict(lambda: {"correct": 0, "total": 0})

    correct_per_game = []
    correct_pct_per_game = []

    for game in games:
        game_correct = 0
        game_answered = 0
        for clue in game["clues"]:
            result = clue["result"]
            value = int(clue["value"])
            round_name = clue["round"]

            if result == "u":
                unrevealed_count += 1
                continue

            if result == "c":
                correct_count += 1
                game_correct += 1
                game_answered += 1
            elif result == "w":
                wrong_count += 1
                game_answered += 1
            elif result == ".":
                skipped_count += 1
            elif result == "dc":
                correct_count += 1
                dd_correct += 1
                game_correct += 1
                game_answered += 1
            elif result == "dw":
                wrong_count += 1
                dd_wrong += 1
                game_answered += 1

            value_accuracy[value]["total"] += 1
            if result in ("c", "dc"):
                value_accuracy[value]["correct"] += 1

            round_accuracy[round_name]["total"] += 1
            if result in ("c", "dc"):
                round_accuracy[round_name]["correct"] += 1

        correct_per_game.append(game_correct)
        pct = round(100 * game_correct / game_answered, 1) if game_answered > 0 else 0
        correct_pct_per_game.append(pct)

    # Accuracy excludes skipped and unrevealed per spec: (c + dc) / (c + w + dc + dw)
    total_answered = correct_count + wrong_count
    best_date = max(game_scores, key=game_scores.get)

    stats = {
        "games_played": len(games),
        "avg_coryat": round(sum(coryats) / len(coryats), 0),
        "best_coryat": max(coryats),
        "best_coryat_date": best_date,
        "worst_coryat": min(coryats),
        "correct": correct_count,
        "wrong": wrong_count,
        "skipped": skipped_count,
        "unrevealed": unrevealed_count,
        "accuracy_pct": round(100 * correct_count / total_answered, 1) if total_answered > 0 else 0,
        "dd_record": f"{dd_correct}-{dd_wrong}",
        "dd_correct_pct": round(100 * dd_correct / (dd_correct + dd_wrong), 1) if (dd_correct + dd_wrong) > 0 else 0,
        "value_accuracy": dict(value_accuracy),
        "round_accuracy": dict(round_accuracy),
        "coryat_history": [game_scores[game["date"]] for game in games],
        "correct_per_game": correct_per_game,
        "correct_pct_per_game": correct_pct_per_game,
        "dates": [game["date"] for game in games],
    }

    return stats


def format_date_for_display(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        return dt.strftime("%b %d, %Y")
    except Exception:
        return date_str


def generate_html(stats):
    """Generate HTML dashboard."""
    if not stats:
        stats = {
            "games_played": 0,
            "avg_coryat": 0,
            "best_coryat": 0,
            "best_coryat_date": "",
            "worst_coryat": 0,
            "correct": 0,
            "wrong": 0,
            "skipped": 0,
            "unrevealed": 0,
            "accuracy_pct": 0,
            "dd_record": "0-0",
            "dd_correct_pct": 0,
            "value_accuracy": {},
            "round_accuracy": {},
            "coryat_history": [],
            "correct_per_game": [],
            "correct_pct_per_game": [],
            "dates": [],
        }

    dates_formatted = [format_date_for_display(d) for d in stats.get("dates", [])]
    best_date_formatted = format_date_for_display(stats.get("best_coryat_date", ""))

    coryat_history = stats.get("coryat_history", [])
    coryat_rolling = rolling_average(coryat_history, ROLLING_WINDOW)

    value_accuracy_raw = stats.get("value_accuracy", {})
    value_labels = sorted(value_accuracy_raw.keys())
    value_accuracy_pct = [
        round(value_accuracy_raw[v]["correct"] / max(1, value_accuracy_raw[v]["total"]) * 100, 1)
        for v in value_labels
    ]

    round_data_json = json.dumps(stats.get("round_accuracy", {}))
    value_labels_json = json.dumps([f"${v}" for v in value_labels])
    dates_json = json.dumps(dates_formatted)
    coryat_history_json = json.dumps(coryat_history)
    coryat_rolling_json = json.dumps(coryat_rolling)
    correct_per_game_json = json.dumps(stats.get("correct_per_game", []))
    correct_pct_per_game_json = json.dumps(stats.get("correct_pct_per_game", []))
    value_accuracy_json = json.dumps(value_accuracy_pct)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jeopardy Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <style>
        :root {{
            --blue: #0056b3;
            --green: #28a745;
            --red: #dc3545;
            --yellow: #ffc107;
            --gray: #f8f9fa;
            --dark: #333;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, var(--blue) 0%, #0041a8 100%);
            color: var(--dark);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }}
        h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        .timestamp {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            color: var(--blue);
            margin: 10px 0;
        }}
        .stat-card .label {{
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .stat-card .sublabel {{
            font-size: 0.85em;
            color: #999;
            margin-top: 4px;
        }}
        .charts-section {{
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 40px;
        }}
        .chart-container {{
            position: relative;
            height: 300px;
            margin-bottom: 40px;
        }}
        .chart-container h3 {{
            margin-bottom: 15px;
            color: var(--dark);
            font-size: 1.3em;
        }}
        .chart-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
        }}
        .chart-container.half {{
            height: 300px;
        }}
        footer {{
            text-align: center;
            color: white;
            margin-top: 40px;
            font-size: 0.9em;
            opacity: 0.9;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Jeopardy Dashboard</h1>
            <p class="timestamp">Last updated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}</p>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Games Played</div>
                <div class="value">{stats.get('games_played', 0)}</div>
            </div>
            <div class="stat-card">
                <div class="label">Average Coryat</div>
                <div class="value">${stats.get('avg_coryat', 0):,.0f}</div>
            </div>
            <div class="stat-card">
                <div class="label">Best Coryat</div>
                <div class="value" style="color: var(--green);">${stats.get('best_coryat', 0):,.0f}</div>
                <div class="sublabel">{best_date_formatted}</div>
            </div>
            <div class="stat-card">
                <div class="label">All-time Correct %</div>
                <div class="value">{stats.get('accuracy_pct', 0):.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="label">Daily Double Record</div>
                <div class="value">{stats.get('dd_record', '0-0')}</div>
                <div class="sublabel">{stats.get('dd_correct_pct', 0):.0f}% correct</div>
            </div>
        </div>

        <div class="charts-section">
            <div class="chart-container">
                <h3>Coryat Over Time</h3>
                <canvas id="coryatChart"></canvas>
            </div>

            <div class="chart-row">
                <div class="chart-container half">
                    <h3>Number Correct Over Time</h3>
                    <canvas id="correctCountChart"></canvas>
                </div>
                <div class="chart-container half">
                    <h3>Correct % Over Time</h3>
                    <canvas id="correctPctChart"></canvas>
                </div>
            </div>

            <div class="chart-row">
                <div class="chart-container half">
                    <h3>Accuracy by Dollar Value</h3>
                    <canvas id="valueChart"></canvas>
                </div>
                <div class="chart-container half">
                    <h3>Accuracy by Round</h3>
                    <canvas id="roundChart"></canvas>
                </div>
            </div>
        </div>

        <footer>
            <p>Generated by <a href="https://github.com/noahjcase/coryat" style="color: white;">playj</a></p>
        </footer>
    </div>

    <script>
        const coryatCtx = document.getElementById('coryatChart').getContext('2d');
        new Chart(coryatCtx, {{
            type: 'line',
            data: {{
                labels: {dates_json},
                datasets: [
                    {{
                        label: 'Coryat Score',
                        data: {coryat_history_json},
                        borderColor: 'rgba(0, 86, 179, 0.4)',
                        backgroundColor: 'transparent',
                        tension: 0.2,
                        pointRadius: 4,
                        pointBackgroundColor: 'rgba(0, 86, 179, 0.6)',
                    }},
                    {{
                        label: '{ROLLING_WINDOW}-Game Average',
                        data: {coryat_rolling_json},
                        borderColor: '#0056b3',
                        backgroundColor: 'rgba(0, 86, 179, 0.1)',
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0,
                        borderWidth: 2.5,
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: true, position: 'top' }} }},
                scales: {{ y: {{ beginAtZero: false }} }}
            }}
        }});

        const correctCountCtx = document.getElementById('correctCountChart').getContext('2d');
        new Chart(correctCountCtx, {{
            type: 'line',
            data: {{
                labels: {dates_json},
                datasets: [{{
                    label: 'Correct',
                    data: {correct_per_game_json},
                    borderColor: 'var(--green)',
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    tension: 0.3,
                    fill: true,
                    pointRadius: 4,
                    pointBackgroundColor: 'var(--green)',
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{ y: {{ beginAtZero: true }} }}
            }}
        }});

        const correctPctCtx = document.getElementById('correctPctChart').getContext('2d');
        new Chart(correctPctCtx, {{
            type: 'line',
            data: {{
                labels: {dates_json},
                datasets: [{{
                    label: 'Correct %',
                    data: {correct_pct_per_game_json},
                    borderColor: '#17a2b8',
                    backgroundColor: 'rgba(23, 162, 184, 0.1)',
                    tension: 0.3,
                    fill: true,
                    pointRadius: 4,
                    pointBackgroundColor: '#17a2b8',
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{ y: {{ max: 100, beginAtZero: true }} }}
            }}
        }});

        const valueCtx = document.getElementById('valueChart').getContext('2d');
        new Chart(valueCtx, {{
            type: 'bar',
            data: {{
                labels: {value_labels_json},
                datasets: [{{
                    label: 'Correct %',
                    data: {value_accuracy_json},
                    backgroundColor: 'var(--blue)',
                    borderRadius: 5
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{ y: {{ max: 100, beginAtZero: true }} }}
            }}
        }});

        const roundCtx = document.getElementById('roundChart').getContext('2d');
        const roundData = {round_data_json};
        const roundLabels = Object.keys(roundData).map(r => r.charAt(0).toUpperCase() + r.slice(1));
        const roundAccuracy = Object.values(roundData).map(r => r.total > 0 ? r.correct / r.total * 100 : 0);
        new Chart(roundCtx, {{
            type: 'bar',
            data: {{
                labels: roundLabels,
                datasets: [{{
                    label: 'Correct %',
                    data: roundAccuracy,
                    backgroundColor: ['var(--green)', 'var(--blue)'],
                    borderRadius: 5
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{ y: {{ max: 100, beginAtZero: true }} }}
            }}
        }});
    </script>
</body>
</html>
"""

    return html


def main():
    if not GAMES_DIR.exists():
        print(f"Error: {GAMES_DIR} directory not found")
        return

    games, game_scores = parse_games()
    stats = calculate_stats(games, game_scores)
    html = generate_html(stats)

    OUTPUT_FILE.write_text(html)
    print(f"Dashboard generated: {OUTPUT_FILE}")
    print(f"  Games: {stats.get('games_played', 0)}")
    print(f"  Avg Coryat: ${stats.get('avg_coryat', 0):,.0f}")
    print(f"  Accuracy: {stats.get('accuracy_pct', 0):.1f}%")


if __name__ == "__main__":
    main()
