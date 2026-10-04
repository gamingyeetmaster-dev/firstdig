"""Internal daily proof brief for First Dig marketing and sales.

This intentionally summarizes real primary-record data after the daily pipeline refresh.
It is not customer-facing copy and never treats a filing as a customer, endorsement,
or proof that a prospect wants to be contacted.
"""
import datetime as dt
import html
import logging

from .. import config

log = logging.getLogger("marketing-brief")


def _money(value):
    if value is None:
        return "—"
    try:
        return "$" + f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _rows(con, limit=5):
    projects = con.execute(
        """
        SELECT address, neighbourhood, kind, stage, first_filed, est_cost, units_created
        FROM projects
        WHERE first_filed IS NOT NULL
          AND kind IN ('teardown','new_house','multiplex','major_addition','garden_suite')
        ORDER BY first_filed DESC,
                 CASE kind
                   WHEN 'teardown' THEN 1
                   WHEN 'new_house' THEN 2
                   WHEN 'multiplex' THEN 3
                   WHEN 'major_addition' THEN 4
                   ELSE 5
                 END,
                 last_activity DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    openings = con.execute(
        """
        SELECT name, category, address, neighbourhood, first_signal, last_signal,
               signal_count, est_cost
        FROM openings
        WHERE last_signal IS NOT NULL
          AND signal_count >= 2
        ORDER BY last_signal DESC, signal_count DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return projects, openings


TRADE_PROOF_GROUPS = [
    ("Demolition / excavation", ("teardown", "new_house", "major_addition")),
    ("Underpinning / basement", ("underpinning",)),
    ("Pool / landscape adjacency", ("pool", "teardown", "new_house", "major_addition")),
]


def _trade_rows(con, limit=5):
    """Return fresh project slices aligned to the trades First Dig is actively validating."""
    groups = []
    for label, kinds in TRADE_PROOF_GROUPS:
        placeholders = ",".join("?" * len(kinds))
        rows = con.execute(
            f"""
            SELECT address, neighbourhood, kind, stage, first_filed, est_cost, units_created
            FROM projects
            WHERE first_filed IS NOT NULL
              AND first_filed >= date('now','-30 days')
              AND stage IN ('applied','issued','construction')
              AND kind IN ({placeholders})
            ORDER BY first_filed DESC, score DESC, last_activity DESC
            LIMIT ?
            """,
            (*kinds, limit),
        ).fetchall()
        groups.append((label, rows))
    return groups


def render(con, limit=5):
    """Return (subject, html, text) for an internal, evidence-first daily brief."""
    projects, openings = _rows(con, limit=limit)
    trade_groups = _trade_rows(con, limit=limit)
    today = dt.date.today().isoformat()
    subject = f"First Dig daily proof brief — {today}"

    text_lines = [
        "FIRST DIG — INTERNAL DAILY PROOF BRIEF",
        "",
        "Use these records as leads for verification and product-proof ideas only.",
        "Do not imply customer status, consent, endorsement, or demand.",
        "",
        "TEARDOWN FEED — freshest high-value project stages",
    ]
    project_html = []
    for r in projects:
        line = (
            f"{r['first_filed'] or '—'} | {r['address'] or '—'} | "
            f"{r['neighbourhood'] or '—'} | {r['kind'] or '—'} | "
            f"{r['stage'] or '—'} | declared cost {_money(r['est_cost'])}"
        )
        text_lines.append(line)
        project_html.append(
            "<tr>"
            f"<td>{html.escape(str(r['first_filed'] or '—'))}</td>"
            f"<td>{html.escape(str(r['address'] or '—'))}</td>"
            f"<td>{html.escape(str(r['neighbourhood'] or '—'))}</td>"
            f"<td>{html.escape(str(r['kind'] or '—'))}</td>"
            f"<td>{html.escape(str(r['stage'] or '—'))}</td>"
            f"<td>{html.escape(_money(r['est_cost']))}</td>"
            "</tr>"
        )

    text_lines += ["", "TRADE-SPECIFIC PROOF — freshest matching project signals"]
    trade_html_sections = []
    for label, rows in trade_groups:
        text_lines += ["", label.upper()]
        if not rows:
            text_lines.append("No matching project in the last 30 days.")
            trade_html_sections.append(
                f"<h3 style=\"font-size:16px;margin:18px 0 8px\">{html.escape(label)}</h3>"
                '<p style="color:#667085">No matching project in the last 30 days.</p>'
            )
            continue
        rendered_rows = []
        for r in rows:
            line = (
                f"{r['first_filed'] or '—'} | {r['address'] or '—'} | "
                f"{r['neighbourhood'] or '—'} | {r['kind'] or '—'} | "
                f"{r['stage'] or '—'} | declared cost {_money(r['est_cost'])}"
            )
            text_lines.append(line)
            rendered_rows.append(
                "<tr>"
                f"<td>{html.escape(str(r['first_filed'] or '—'))}</td>"
                f"<td>{html.escape(str(r['address'] or '—'))}</td>"
                f"<td>{html.escape(str(r['neighbourhood'] or '—'))}</td>"
                f"<td>{html.escape(str(r['kind'] or '—'))}</td>"
                f"<td>{html.escape(str(r['stage'] or '—'))}</td>"
                f"<td>{html.escape(_money(r['est_cost']))}</td>"
                "</tr>"
            )
        trade_html_sections.append((label, rendered_rows))

    text_lines += ["", "OPENING SOON — freshest multi-signal records"]
    opening_html = []
    for r in openings:
        label = r["name"] or r["category"] or "Unnamed filing"
        line = (
            f"{r['last_signal'] or '—'} | {label} | {r['address'] or '—'} | "
            f"{r['neighbourhood'] or '—'} | {r['signal_count'] or 0} signal(s)"
        )
        text_lines.append(line)
        opening_html.append(
            "<tr>"
            f"<td>{html.escape(str(r['last_signal'] or '—'))}</td>"
            f"<td>{html.escape(str(label))}</td>"
            f"<td>{html.escape(str(r['address'] or '—'))}</td>"
            f"<td>{html.escape(str(r['neighbourhood'] or '—'))}</td>"
            f"<td>{html.escape(str(r['signal_count'] or 0))}</td>"
            "</tr>"
        )

    text_lines += [
        "",
        "EDITORIAL GATE",
        "Before publishing a record publicly, verify the source is fresh and avoid personal contact details.",
        "For commercial outreach, separately verify the recipient, relevance, consent basis, identification, mailing address, and unsubscribe requirements.",
    ]

    styles = (
        "font-family:Arial,Helvetica,sans-serif;border-collapse:collapse;width:100%;"
        "font-size:13px"
    )
    th = "text-align:left;border-bottom:2px solid #0e1a2b;padding:7px 8px"
    td = "border-bottom:1px solid #d7dde5;padding:7px 8px;vertical-align:top"
    table_project = (
        f'<table style="{styles}"><thead><tr>'
        + "".join(f'<th style="{th}">{x}</th>' for x in ["Filed", "Address", "Area", "Kind", "Stage", "Declared cost"])
        + "</tr></thead><tbody>"
        + "".join(project_html).replace("<td>", f'<td style="{td}">')
        + "</tbody></table>"
    )
    trade_tables = []
    for section in trade_html_sections:
        if isinstance(section, str):
            trade_tables.append(section)
            continue
        label, rendered_rows = section
        trade_tables.append(
            f'<h3 style="font-size:16px;margin:18px 0 8px">{html.escape(label)}</h3>'
            + f'<table style="{styles}"><thead><tr>'
            + "".join(f'<th style="{th}">{x}</th>' for x in ["Filed", "Address", "Area", "Kind", "Stage", "Declared cost"])
            + "</tr></thead><tbody>"
            + "".join(rendered_rows).replace("<td>", f'<td style="{td}">')
            + "</tbody></table>"
        )
    table_trade = "".join(trade_tables)

    table_opening = (
        f'<table style="{styles}"><thead><tr>'
        + "".join(f'<th style="{th}">{x}</th>' for x in ["Signal", "Business / category", "Address", "Area", "Signals"])
        + "</tr></thead><tbody>"
        + "".join(opening_html).replace("<td>", f'<td style="{td}">')
        + "</tbody></table>"
    )
    html_body = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;color:#0e1a2b;max-width:900px;margin:auto">
      <div style="border-bottom:4px solid #0e1a2b;padding:8px 0 14px">
        <div style="font-size:12px;letter-spacing:.08em">FIRST DIG · INTERNAL</div>
        <h1 style="font-size:28px;margin:8px 0 0">Daily proof brief</h1>
        <div style="color:#46566b">{today}</div>
      </div>
      <p style="background:#f2f4f7;padding:12px 14px;border:1px solid #d7dde5">
        Real primary-record data for verification, product proof and targeted research.
        A filing is <strong>not</strong> a customer, endorsement, consent signal or proof of demand.
      </p>
      <h2 style="font-size:20px;margin-top:28px">Teardown Feed — freshest high-value project stages</h2>
      {table_project}
      <h2 style="font-size:20px;margin-top:28px">Trade-specific proof — freshest matching project signals</h2>
      {table_trade}
      <h2 style="font-size:20px;margin-top:28px">Opening Soon — freshest multi-signal records</h2>
      {table_opening}
      <h2 style="font-size:20px;margin-top:28px">Editorial gate</h2>
      <p>Before publishing a record, verify freshness and avoid personal contact details.
      Before commercial outreach, separately verify recipient relevance and the applicable
      consent, identification, mailing-address and unsubscribe requirements.</p>
    </div>
    """
    return subject, html_body, "\n".join(text_lines)


def send(con, send_fn, log_fn=log.info):
    to = config.MARKETING_BRIEF_TO
    if not to:
        return False
    subject, html_body, text_body = render(con)
    result = send_fn(to, subject, html_body, text_body)
    if result.get("delivered"):
        log_fn(f"marketing brief: sent to {to}")
        return True
    log_fn(f"marketing brief: send failed: {result.get('error') or 'unknown error'}")
    return False
