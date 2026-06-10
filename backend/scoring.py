import sqlite3
import os
import re
import math

DB_FILE = os.path.join(os.path.dirname(__file__), "engine.db")

def parse_currency(val_str):
    if not val_str or val_str == "None" or val_str == "nan":
        return 0.0
    val_str = str(val_str).upper().replace(",", "").strip()
    match = re.search(r'(?:PKR|USD)?\s*([\d\.]+)\s*([M|K|B]?)', val_str)
    if not match:
        return 0.0
    try:
        val = float(match.group(1))
        suffix = match.group(2)
        if suffix == 'M':
            return val * 1_000_000
        elif suffix == 'K':
            return val * 1_000
        elif suffix == 'B':
            return val * 1_000_000_000
        return val
    except Exception:
        return 0.0

class WinProbabilityScorer:
    def __init__(self):
        self.db_path = DB_FILE
        self._load_historic_stats()
        
    def _load_historic_stats(self):
        self.sector_stats = {}
        self.overall_win_rate = 0.5
        self.avg_win_budget = 100_000_000.0
        
        if not os.path.exists(self.db_path):
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. Sector Win Rates
            cursor.execute("SELECT sector, outcome, budget FROM bid_history")
            rows = cursor.fetchall()
            
            sector_wins = {}
            sector_totals = {}
            winning_budgets = []
            
            for row in rows:
                sector = row["sector"]
                outcome = row["outcome"]
                budget = parse_currency(row["budget"])
                
                sector_totals[sector] = sector_totals.get(sector, 0) + 1
                if outcome.strip().lower() == "win":
                    sector_wins[sector] = sector_wins.get(sector, 0) + 1
                    if budget > 0:
                        winning_budgets.append(budget)
            
            for sector in sector_totals:
                wins = sector_wins.get(sector, 0)
                total = sector_totals[sector]
                self.sector_stats[sector] = wins / total
                
            total_wins = sum(sector_wins.values())
            total_bids = sum(sector_totals.values())
            if total_bids > 0:
                self.overall_win_rate = total_wins / total_bids
            if winning_budgets:
                self.avg_win_budget = sum(winning_budgets) / len(winning_budgets)
                
            conn.close()
        except Exception as e:
            print("Error loading historical stats:", e)

    def calculate_score(self, sector, budget_str, compliance_pct, gaps_count, competitor_count=2):
        # 1. Sector Win Rate (weight: 0.3)
        sector_win_rate = self.sector_stats.get(sector, self.overall_win_rate)
        
        # 2. Budget Score (weight: 0.2)
        # Assumes target budget within 0.5x to 2x of average winning budget is ideal.
        target_budget = parse_currency(budget_str)
        if target_budget == 0.0 or self.avg_win_budget == 0.0:
            budget_score = 0.5
        else:
            ratio = target_budget / self.avg_win_budget
            if 0.5 <= ratio <= 2.0:
                budget_score = 1.0
            elif ratio < 0.5:
                budget_score = ratio * 2.0  # Scales down
            else:
                budget_score = max(0.0, 2.0 - (ratio / 2.0))
                
        # 3. Compliance Score (weight: 0.3)
        # Scales compliance directly
        compliance_score = compliance_pct / 100.0
        
        # 4. Gaps Penalty (weight: 0.2)
        # More gaps lowers the score. Each gap is -10% up to 100%
        gaps_score = max(0.0, 1.0 - (gaps_count * 0.15))
        
        # 5. Competitor Penalty
        # -5% win probability per competitor
        competitor_penalty = competitor_count * 0.04
        
        # Weighted Score
        weighted_score = (
            0.3 * sector_win_rate +
            0.2 * budget_score +
            0.3 * compliance_score +
            0.2 * gaps_score
        ) - competitor_penalty
        
        # Normalize between 0 and 100
        final_probability = max(0.0, min(1.0, weighted_score)) * 100.0
        
        # Go/No-Go Decision recommendation threshold: 65%
        decision = "GO" if final_probability >= 65.0 else "NO-GO"
        
        return {
            "win_probability": round(final_probability, 1),
            "decision": decision,
            "breakdown": {
                "sector_win_rate": round(sector_win_rate * 100, 1),
                "budget_fit": round(budget_score * 100, 1),
                "compliance_fit": round(compliance_score * 100, 1),
                "gaps_score": round(gaps_score * 100, 1),
                "competitor_penalty": round(competitor_penalty * 100, 1)
            }
        }

if __name__ == "__main__":
    scorer = WinProbabilityScorer()
    print("Test Scoring for IT Services, 20M PKR, 85% compliance, 2 gaps:")
    print(scorer.calculate_score("IT Services", "PKR 20M", 85, 2))
