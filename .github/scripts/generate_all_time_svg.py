import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

TOKEN = os.environ["GITHUB_TOKEN"]
USER = os.environ["GITHUB_USER"]


def gql(query: str, variables: dict) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "all-time-contribution-chart",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    if "errors" in data:
        raise RuntimeError(f"GitHub GraphQL error: {data['errors']}")
    return data["data"]


def nice_ceil(val: int) -> int:
    if val <= 4:
        return 4
    step = max(1, (val + 3) // 4)
    mag = 10 ** (len(str(step)) - 1)
    for mult in (1, 2, 5, 10):
        if mult * mag >= step:
            return mult * mag * 4
    return step * 4


def render_svg(keys: list[str], vals: list[int], total: int, dark: bool) -> str:
    w, h = 880, 290
    pad_l, pad_r, pad_t, pad_b = 58, 28, 72, 44
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    bg = "#0D1117" if dark else "#FFFFFF"
    border = "#30363D" if dark else "#E2E8F0"
    title_col = "#2DD4BF" if dark else "#0F766E"
    sub_col = "#94A3B8" if dark else "#64748B"
    grid_col = "#30363D" if dark else "#E2E8F0"
    axis_col = "#94A3B8" if dark else "#64748B"
    line_col = "#2DD4BF" if dark else "#0F766E"
    ma_col = "#FB923C" if dark else "#EA580C"
    dot_bg = "#0D1117" if dark else "#FFFFFF"

    y_max = nice_ceil(max(vals) if vals else 0)

    ma_vals = []
    for i in range(len(vals)):
        window = vals[max(0, i - 2) : i + 1]
        ma_vals.append(sum(window) / len(window))

    def to_xy(idx: int, v: float) -> tuple[float, float]:
        x = pad_l + (idx / max(len(vals) - 1, 1)) * plot_w
        y = pad_t + plot_h - (v / y_max) * plot_h
        return x, y

    pts = [to_xy(i, v) for i, v in enumerate(vals)]
    ma_pts = [to_xy(i, v) for i, v in enumerate(ma_vals)]

    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d = f"{line_d} L {pts[-1][0]:.1f},{pad_t + plot_h:.1f} L {pts[0][0]:.1f},{pad_t + plot_h:.1f} Z"
    ma_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in ma_pts)

    grid_lines = []
    for k in range(5):
        tick_v = (y_max * k) // 4
        gy = pad_t + plot_h - (k / 4) * plot_h
        grid_lines.append(
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{w - pad_r}" y2="{gy:.1f}" '
            f'stroke="{grid_col}" stroke-width="1" stroke-dasharray="{"0" if k == 0 else "3,4"}"/>'
            f'<text x="{pad_l - 10}" y="{gy + 4:.1f}" text-anchor="end" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="11" fill="{axis_col}">{tick_v}</text>'
        )

    n = len(keys)
    x_indices = list(range(n)) if n <= 7 else sorted({round(i * (n - 1) / 6) for i in range(7)})
    x_labels = [
        f'<text x="{pts[i][0]:.1f}" y="{h - 16}" text-anchor="middle" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="11" fill="{axis_col}">{keys[i]}</text>'
        for i in x_indices
    ]

    peak_i = max(range(len(vals)), key=lambda i: vals[i])
    px, py = pts[peak_i]
    dots = [
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{dot_bg}" stroke="{line_col}" stroke-width="2"/>'
        for i, (x, y) in enumerate(pts)
        if i != peak_i
    ]
    dots.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="{ma_col}" stroke="{dot_bg}" stroke-width="1.5"/>')

    avg_m = total / max(len(vals), 1)
    peak_label = f"{vals[peak_i]} ({keys[peak_i]})"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%">
  <defs>
    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{line_col}" stop-opacity="0.32"/>
      <stop offset="100%" stop-color="{line_col}" stop-opacity="0.02"/>
    </linearGradient>
  </defs>
  <rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="8" fill="{bg}" stroke="{border}"/>
  <text x="{pad_l}" y="28" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="13" font-weight="700" letter-spacing="0.6" fill="{title_col}">ALL-TIME CONTRIBUTION TIME SERIES</text>
  <text x="{pad_l}" y="47" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="12" fill="{sub_col}">{keys[0]} to {keys[-1]}  ·  {total:,} total  ·  {avg_m:.1f}/mo avg  ·  Peak: {peak_label}</text>
  <g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="11" fill="{sub_col}">
    <line x1="{w - 230}" y1="24" x2="{w - 210}" y2="24" stroke="{line_col}" stroke-width="2.5"/>
    <text x="{w - 204}" y="28">Monthly</text>
    <line x1="{w - 135}" y1="24" x2="{w - 115}" y2="24" stroke="{ma_col}" stroke-width="2" stroke-dasharray="5,3"/>
    <text x="{w - 109}" y="28">3-Mo MA</text>
  </g>
  {"".join(grid_lines)}
  <path d="{area_d}" fill="url(#areaGrad)"/>
  <path d="{line_d}" fill="none" stroke="{line_col}" stroke-width="2.4" stroke-linejoin="round"/>
  <path d="{ma_d}" fill="none" stroke="{ma_col}" stroke-width="2" stroke-dasharray="5,3" stroke-linejoin="round"/>
  {"".join(dots)}
  {"".join(x_labels)}
</svg>
"""


def main() -> None:
    created_iso = gql(
        "query($login: String!) { user(login: $login) { createdAt } }",
        {"login": USER},
    )["user"]["createdAt"]
    created_dt = datetime.fromisoformat(created_iso.replace("Z", "+00:00"))
    created_date = created_dt.strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc)
    today_date = now.strftime("%Y-%m-%d")

    contrib_q = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    monthly: dict[str, int] = defaultdict(int)
    total = 0

    for year in range(created_dt.year, now.year + 1):
        f_dt = created_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if year == created_dt.year else f"{year}-01-01T00:00:00Z"
        t_dt = now.strftime("%Y-%m-%dT%H:%M:%SZ") if year == now.year else f"{year}-12-31T23:59:59Z"
        cal = gql(contrib_q, {"login": USER, "from": f_dt, "to": t_dt})["user"]["contributionsCollection"]["contributionCalendar"]
        total += cal["totalContributions"]
        for week in cal["weeks"]:
            for day in week["contributionDays"]:
                d = day["date"]
                if created_date <= d <= today_date:
                    monthly[d[:7]] += day["contributionCount"]

    keys = sorted(monthly.keys()) or [now.strftime("%Y-%m")]
    vals = [monthly[k] for k in keys]

    os.makedirs("assets", exist_ok=True)
    for dark, fname in ((False, "all-time-contributions-light.svg"), (True, "all-time-contributions-dark.svg")):
        with open(os.path.join("assets", fname), "w", encoding="utf-8") as f:
            f.write(render_svg(keys, vals, total, dark=dark))


if __name__ == "__main__":
    main()
