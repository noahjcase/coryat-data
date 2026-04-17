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


def parse_games():
    """Parse all game CSVs and return aggregated stats."""
    games = []
    game_scores = {}  # date -> coryat score

    for csv_file in sorted(GAMES_DIR.glob("*.csv")):
        date_str = csv_file.stem
        clues = []

        with open(csv_file, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                clues.append(row)

        # Calculate Coryat for this game
        coryat = 0
        for clue in clues:
            value = int(clue["value"])
            result = clue["result"]
            if result in ("c", "dc"):
                coryat += value
            elif result in ("x", "dx"):
                coryat -= value

        game_scores[date_str] = coryat
        games.append({"date": date_str, "clues": clues, "coryat": coryat})

    return games, game_scores


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
    dd_skipped = 0
    category_accuracy = defaultdict(lambda: {"correct": 0, "total": 0})
    value_accuracy = defaultdict(lambda: {"correct": 0, "total": 0})
    round_accuracy = defaultdict(lambda: {"correct": 0, "total": 0})

    for game in games:
        for clue in game["clues"]:
            result = clue["result"]
            value = int(clue["value"])
            category = clue["category"]
            round_name = clue["round"]

            # Skip unrevealed clues
            if result == "u":
                unrevealed_count += 1
                continue

            # Count by result
            if result == "c":
                correct_count += 1
            elif result == "x":
                wrong_count += 1
            elif result == ".":
                skipped_count += 1
            elif result == "dc":
                correct_count += 1
                dd_correct += 1
            elif result == "dx":
                wrong_count += 1
                dd_wrong += 1
            elif result == "d.":
                skipped_count += 1
                dd_skipped += 1

            # Accuracy by category
            category_accuracy[category]["total"] += 1
            if result in ("c", "dc"):
                category_accuracy[category]["correct"] += 1

            # Accuracy by value
            value_accuracy[value]["total"] += 1
            if result in ("c", "dc"):
                value_accuracy[value]["correct"] += 1

            # Accuracy by round
            round_accuracy[round_name]["total"] += 1
            if result in ("c", "dc"):
                round_accuracy[round_name]["correct"] += 1

    total_answered = correct_count + wrong_count + skipped_count
    total_clues = total_answered + unrevealed_count

    stats = {
        "games_played": len(games),
        "avg_coryat": round(sum(coryats) / len(coryats), 0),
        "best_coryat": max(coryats),
        "worst_coryat": min(coryats),
        "total_coryat": sum(coryats),
        "correct": correct_count,
        "wrong": wrong_count,
        "skipped": skipped_count,
        "unrevealed": unrevealed_count,
        "accuracy_pct": round(100 * correct_count / total_answered, 1) if total_answered > 0 else 0,
        "dd_record": f"{dd_correct}-{dd_wrong}",
        "dd_win_pct": round(100 * dd_correct / (dd_correct + dd_wrong), 1) if (dd_correct + dd_wrong) > 0 else 0,
        "category_accuracy": dict(category_accuracy),
        "value_accuracy": dict(value_accuracy),
        "round_accuracy": dict(round_accuracy),
        "coryat_history": [game_scores[game["date"]] for game in games],
        "dates": [game["date"] for game in games],
    }

    return stats


def format_date_for_display(date_str):
    """Convert YYYYMMDD to readable format."""
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        return dt.strftime("%b %d, %Y")
    except:
        return date_str


def generate_html(stats):
    """Generate HTML dashboard."""
    if not stats:
        stats = {
            "games_played": 0,
            "avg_coryat": 0,
            "best_coryat": 0,
            "worst_coryat": 0,
            "total_coryat": 0,
            "correct": 0,
            "wrong": 0,
            "skipped": 0,
            "unrevealed": 0,
            "accuracy_pct": 0,
            "dd_record": "0-0",
            "dd_win_pct": 0,
            "category_accuracy": {},
            "value_accuracy": {},
            "round_accuracy": {},
            "coryat_history": [],
            "dates": [],
        }

    dates_formatted = [format_date_for_display(d) for d in stats.get("dates", [])]
    value_labels = sorted(stats.get("value_accuracy", {}).keys())
    value_accuracy = [stats["value_accuracy"].get(str(v), {}).get("correct", 0) / max(1, stats["value_accuracy"].get(str(v), {}).get("total", 1)) * 100 for v in value_labels]

    category_names = list(stats.get("category_accuracy", {}).keys())
    category_accuracy = [stats["category_accuracy"][cat].get("correct", 0) / max(1, stats["category_accuracy"][cat].get("total", 1)) * 100 for cat in category_names]

    round_data_json = json.dumps(stats.get('round_accuracy', {}))
    value_labels_json = json.dumps([f"${v}" for v in value_labels])
    dates_json = json.dumps(dates_formatted)
    coryat_history_json = json.dumps(stats.get('coryat_history', []))
    category_names_json = json.dumps(category_names[:10])
    category_accuracy_json = json.dumps(category_accuracy[:10])
    value_accuracy_json = json.dumps(value_accuracy)

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
            <h1>🎬 Jeopardy Dashboard</h1>
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
            </div>
            <div class="stat-card">
                <div class="label">Accuracy</div>
                <div class="value">{stats.get('accuracy_pct', 0):.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="label">Daily Double Record</div>
                <div class="value">{stats.get('dd_record', '0-0')}</div>
                <div class="label" style="margin-top: 5px;">{stats.get('dd_win_pct', 0):.0f}% Win Rate</div>
            </div>
        </div>

        <div class="charts-section">
            <div class="chart-row">
                <div class="chart-container half">
                    <h3>Coryat Trend</h3>
                    <canvas id="coryatChart"></canvas>
                </div>
                <div class="chart-container half">
                    <h3>Accuracy by Round</h3>
                    <canvas id="roundChart"></canvas>
                </div>
            </div>

            <div class="chart-row">
                <div class="chart-container half">
                    <h3>Accuracy by Dollar Value</h3>
                    <canvas id="valueChart"></canvas>
                </div>
                <div class="chart-container half">
                    <h3>Accuracy by Category</h3>
                    <canvas id="categoryChart"></canvas>
                </div>
            </div>
        </div>

        <footer>
            <p>📊 Generated by <a href="https://github.com/noahjcase/coryat" style="color: white;">playj</a></p>
        </footer>
    </div>

    <script>
        const coryatCtx = document.getElementById('coryatChart').getContext('2d');
        new Chart(coryatCtx, {{
            type: 'line',
            data: {{
                labels: {dates_json},
                datasets: [{{
                    label: 'Coryat Score',
                    data: {coryat_history_json},
                    borderColor: 'var(--blue)',
                    backgroundColor: 'rgba(0, 86, 179, 0.1)',
                    tension: 0.3,
                    fill: true,
                    pointRadius: 5,
                    pointBackgroundColor: 'var(--blue)',
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{ y: {{ beginAtZero: false }} }}
            }}
        }});

        const roundCtx = document.getElementById('roundChart').getContext('2d');
        const roundData = {round_data_json}
        const roundLabels = Object.keys(roundData).map(r => r.charAt(0).toUpperCase() + r.slice(1));
        const roundAccuracy = Object.values(roundData).map(r => r.correct / r.total * 100);
        new Chart(roundCtx, {{
            type: 'bar',
            data: {{
                labels: roundLabels,
                datasets: [{{
                    label: 'Accuracy %',
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

        const valueCtx = document.getElementById('valueChart').getContext('2d');
        new Chart(valueCtx, {{
            type: 'bar',
            data: {{
                labels: {value_labels_json},
                datasets: [{{
                    label: 'Accuracy %',
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

        const categoryCtx = document.getElementById('categoryChart').getContext('2d');
        new Chart(categoryCtx, {{
            type: 'doughnut',
            data: {{
                labels: {category_names_json},
                datasets: [{{
                    data: {category_accuracy_json},
                    backgroundColor: [
                        'var(--blue)', 'var(--green)', 'var(--yellow)', '#17a2b8', '#6f42c1',
                        '#e83e8c', '#fd7e14', '#28a745', '#20c997', '#0dcaf0'
                    ],
                    borderColor: 'white',
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ position: 'bottom' }} }}
            }}
        }});
    </script>
</body>
</html>
"""

    return html


def main():
    """Main entry point."""
    if not GAMES_DIR.exists():
        print(f"Error: {GAMES_DIR} directory not found")
        return

    games, game_scores = parse_games()
    stats = calculate_stats(games, game_scores)
    html = generate_html(stats)

    OUTPUT_FILE.write_text(html)
    print(f"✓ Dashboard generated: {OUTPUT_FILE}")
    print(f"  Games: {stats.get('games_played', 0)}")
    print(f"  Avg Coryat: ${stats.get('avg_coryat', 0):,.0f}")
    print(f"  Accuracy: {stats.get('accuracy_pct', 0):.1f}%")


if __name__ == "__main__":
    main()
