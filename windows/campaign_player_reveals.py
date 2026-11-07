"""Read DM-revealed campaign content using the player's authenticated client.

The database RLS is authoritative: never use a service-role key in this client.
"""


def _rows(response):
    return response if isinstance(response, list) else []


def load_player_reveals(client, campaign_id, campaign_character_id=None):
    """Return (visible hooks/entries, effects for *this* linked character only)."""
    campaign_id = str(campaign_id or '').strip()
    if not campaign_id or client is None:
        return [], []
    entries = _rows(client._request_json(
        'GET', '/rest/v1/campaign_entries',
        query={
            'campaign_id': f'eq.{campaign_id}',
            'visible_to_players': 'eq.true',
            'select': 'id,entry_type,title,body,status,updated_at',
            'order': 'updated_at.desc',
            'limit': '100',
        },
    ))
    effects = []
    character_id = str(campaign_character_id or '').strip()
    if character_id:
        effects = _rows(client._request_json(
            'GET', '/rest/v1/campaign_character_effects',
            query={
                'campaign_id': f'eq.{campaign_id}',
                'campaign_character_id': f'eq.{character_id}',
                'visible_to_player': 'eq.true',
                'select': 'id,name,description,status,updated_at',
                'order': 'updated_at.desc',
                'limit': '100',
            },
        ))
    return entries, effects


def format_entries(rows):
    if not rows:
        return 'The DM has not shared any hooks or clues yet.'
    messages = []
    for item in rows:
        title = str(item.get('title') or 'Untitled').strip()
        kind = str(item.get('entry_type') or 'Hook').replace('_', ' ').title()
        details = str(item.get('body') or '').strip()
        status = str(item.get('status') or '').strip()
        headline = f'{kind} · {title}' + (f'  [{status}]' if status else '')
        messages.append(headline + (f'\n{details}' if details else ''))
    return '\n\n'.join(messages)


def format_effects(rows, linked):
    if not linked:
        return 'Link your character to this campaign to see any DM-shared effects.'
    if not rows:
        return 'The DM has not shared any effects for this character.'
    messages = []
    for item in rows:
        name = str(item.get('name') or 'Effect').strip()
        details = str(item.get('description') or '').strip()
        status = str(item.get('status') or '').strip()
        headline = name + (f'  [{status}]' if status else '')
        messages.append(headline + (f'\n{details}' if details else ''))
    return '\n\n'.join(messages)
