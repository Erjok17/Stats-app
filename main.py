from pathlib import Path
from nba_api.stats.endpoints import playbyplayv3
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

GAME_ID = "0022300001"


def fetch_pbp(game_id: str, save: bool = True) -> pd.DataFrame:
    """Fetch play-by-play for a game (V3 endpoint) and cache as CSV."""
    pbp = playbyplayv3.PlayByPlayV3(game_id=game_id)
    df = pbp.get_data_frames()[0]

    if save:
        out = DATA_DIR / f"pbp_{game_id}.csv"
        df.to_csv(out, index=False)
        print(f"Saved {len(df)} rows to {out}")

    return df


if __name__ == "__main__":
    df = fetch_pbp(GAME_ID)
    print("\nColumns:")
    print(list(df.columns))
    print(f"\nShape: {df.shape}")
    print("\nPreview:")
    print(df.head())