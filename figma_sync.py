import os
import re
import sys

import requests


def require_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


FIGMA_TOKEN = require_env("FIGMA_TOKEN")
FIGMA_FILE_KEY = require_env("FIGMA_FILE_KEY")

CONFLUENCE_DOMAIN = require_env("CONFLUENCE_DOMAIN")
CONFLUENCE_EMAIL = require_env("CONFLUENCE_EMAIL")
CONFLUENCE_API_TOKEN = require_env("CONFLUENCE_API_TOKEN")
CONFLUENCE_PAGE_ID = require_env("CONFLUENCE_PAGE_ID")


def clean_page_name(name):
    """Display name cleanup: remove emoji, parentheses, and spaces."""
    if not name:
        return ""
    name = re.sub(r"[^\x00-\x7F]+", "", name)
    name = name.replace("(SP가이드보충예정)", "")
    name = re.sub(r"\(.*?\)", "", name)
    name = re.sub(r"\s+", "", name)
    return name.strip()


def standardize_for_compare(text):
    """Normalize strings to detect duplicates more reliably."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^\x00-\x7F]+", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    std = re.sub(r"\s+", "", text).lower().strip()
    alias_map = {
        "iconbutton": "button",
        "boxbutton": "button",
        "textbutton": "button",
        "floatingactionbutton": "button",
        "emptystate": "empty",
    }
    return alias_map.get(std, std)


def has_design_only_layer(node_detail):
    """Check whether the node contains a design-only marker layer."""
    children = node_detail.get("children", [])
    for child in children:
        child_name = child.get("name", "").strip()
        if "디자인만 컴포넌트" in child_name:
            return True
        if "children" in child and has_design_only_layer(child):
            return True
    return False


def figma_get(url):
    response = requests.get(url, headers={"X-Figma-Token": FIGMA_TOKEN}, timeout=30)
    response.raise_for_status()
    return response.json()


def confluence_get(url):
    response = requests.get(
        url,
        auth=(CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def confluence_put(url, payload):
    response = requests.put(
        url,
        auth=(CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN),
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_figma_components():
    print("1. Figma data analysis started.")
    url = f"https://api.figma.com/v1/files/{FIGMA_FILE_KEY}?depth=1"
    res = figma_get(url)
    pages = res.get("document", {}).get("children", [])

    base_candidates = []
    is_collecting = False

    for page in pages:
        name = page.get("name", "")
        if "Component" in name or "Button" in name:
            is_collecting = True
            continue
        if is_collecting and ("🥑" in name or "💎" in name or "---" in name):
            break
        if is_collecting and "↪️" in name:
            display_name = clean_page_name(name)
            if display_name:
                base_candidates.append({"id": page["id"], "display_name": display_name})

    if not base_candidates:
        print("No base candidates found.")
        return []

    print(f"2. Inspecting design-only layers for {len(base_candidates)} candidates.")

    candidate_ids = [item["id"] for item in base_candidates]
    final_found_list = []
    excluded_names = []

    for i in range(0, len(candidate_ids), 100):
        chunk = candidate_ids[i : i + 100]
        nodes_url = f"https://api.figma.com/v1/files/{FIGMA_FILE_KEY}/nodes?ids={','.join(chunk)}"
        nodes_res = figma_get(nodes_url)
        nodes_data = nodes_res.get("nodes", {})

        for candidate in base_candidates:
            node_id = candidate["id"]
            if node_id not in chunk or node_id not in nodes_data:
                continue

            node_detail = nodes_data[node_id].get("document", {})
            if has_design_only_layer(node_detail):
                excluded_names.append(candidate["display_name"])
                continue

            if candidate["display_name"] not in final_found_list:
                final_found_list.append(candidate["display_name"])

    if excluded_names:
        print(
            "Excluded design-only items: "
            + ", ".join(excluded_names)
        )

    print(
        f"3. Finalized {len(final_found_list)} items "
        f"after filtering {len(excluded_names)} candidates."
    )
    return final_found_list


def get_status_macro(text, color="Green"):
    return (
        '<ac:structured-macro ac:name="status">'
        f'<ac:parameter ac:name="colour">{color}</ac:parameter>'
        f'<ac:parameter ac:name="title">{text}</ac:parameter>'
        "</ac:structured-macro>"
    )


def append_only_new_items(figma_names):
    get_url = (
        f"https://{CONFLUENCE_DOMAIN}/wiki/api/v2/pages/"
        f"{CONFLUENCE_PAGE_ID}?body-format=storage"
    )

    print("4. Comparing against Confluence page.")
    res = confluence_get(get_url)
    current_body = res["body"]["storage"]["value"]

    all_tables = re.findall(r"(<table[^>]*>.*?</table>)", current_body, re.DOTALL | re.IGNORECASE)
    target_table = None
    for table in all_tables:
        if "Android/web" in table:
            target_table = table
            break

    if not target_table:
        raise RuntimeError("Target table containing 'Android/web' was not found.")

    existing_text_pure = re.sub(r"<[^>]+>", "", target_table)
    existing_text_std = standardize_for_compare(existing_text_pure)

    new_items = []
    for name in figma_names:
        std_name = standardize_for_compare(name)
        if std_name not in existing_text_std:
            new_items.append(name)

    if not new_items:
        print("No new items to append.")
        return False

    print(f"5. Appending {len(new_items)} new items to Confluence.")

    new_rows_html = ""
    status_badge = get_status_macro("x", "Red")
    for name in new_items:
        new_rows_html += f"""
        <tr>
            <td><p>{name}</p></td>
            <td style="text-align: center;"><p>{status_badge}</p></td>
            <td style="text-align: center;"><p>{status_badge}</p></td>
            <td style="text-align: center;"><p>{status_badge}</p></td>
        </tr>"""

    if "</tbody>" in target_table:
        updated_table = target_table.replace("</tbody>", f"{new_rows_html}</tbody>")
    else:
        updated_table = target_table.replace("</table>", f"<tbody>{new_rows_html}</tbody></table>")

    updated_body = current_body.replace(target_table, updated_table)
    put_url = f"https://{CONFLUENCE_DOMAIN}/wiki/api/v2/pages/{CONFLUENCE_PAGE_ID}"
    payload = {
        "id": CONFLUENCE_PAGE_ID,
        "status": "current",
        "title": res["title"],
        "body": {"representation": "storage", "value": updated_body},
        "version": {
            "number": res["version"]["number"] + 1,
            "message": "Figma sync: append new components with strict duplicate check",
        },
    }

    confluence_put(put_url, payload)
    return True


def main():
    names = get_figma_components()
    if not names:
        print("No components found. Exiting without update.")
        return 0

    updated = append_only_new_items(names)
    if updated:
        print("Sync completed successfully.")
    else:
        print("Sync finished with no content changes.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Sync failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

