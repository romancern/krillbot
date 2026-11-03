"""Playwright integration for the visible Puffer Party interface."""
import asyncio
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from .store import Store


OVERLAY_COUNTS = {'ordinary': 8, 'specific': 2}

COLORS = {'question': '1;36', 'turn': '34', 'sent': '1;32',
          'result': '33', 'error': '1;31', 'info': '2'}


def log(message, kind='info'):
    label = {'question': '◆', 'turn': '›', 'sent': '➜', 'result': '●',
             'error': '!', 'info': '·'}[kind]
    timestamp = datetime.now().strftime('%H:%M:%S')
    color = sys.stdout.isatty() and not os.environ.get('NO_COLOR')
    if color:
        print(f"\033[2m{timestamp}\033[0m  \033[{COLORS[kind]}m{label} {message}\033[0m", flush=True)
    else:
        print(f'{timestamp}  {label} {message}', flush=True)


def answer_key(answer):
    text = unicodedata.normalize('NFKC', answer).casefold().strip()
    return ' '.join(re.sub(r'[^\w\s]', '', text).split())


def clean_candidates(candidates, excluded=()):
    seen = {answer_key(x) for x in excluded}
    result = []
    for candidate in candidates:
        candidate = ' '.join(candidate.lower().split())
        key = answer_key(candidate)
        if key and key not in seen and len(candidate) <= 60:
            seen.add(key)
            result.append(candidate)
    return result


def clean_groups(groups, excluded=()):
    ordinary = clean_candidates(groups.get('ordinary', []), excluded)
    specific = clean_candidates(groups.get('specific', []), list(excluded) + ordinary)
    return {'ordinary': ordinary, 'specific': specific}


def parse_turn(status):
    text = ' '.join(status.split()).removeprefix('▸').strip()
    if 'your puffer' in text.lower():
        return 'you'
    text = text.rsplit(' · ', 1)[-1]
    match = re.search(r'^(.+?)\s+is up$', text, re.I)
    return match.group(1) if match else None


def current_turn(state):
    turn = parse_turn(state['turn'])
    # The game hides its turn banner while rejection feedback is displayed.
    if not turn and state['input_enabled'] and state['placeholder'] == 'your puffer — type!':
        return 'you'
    return turn


def pending_result(pending, feedback, turn):
    if not pending:
        return None
    if feedback and pending.casefold() in feedback.casefold():
        if 'no echo' in feedback.lower():
            return 'rejected'
        if 'already said' in feedback.lower():
            return 'repeat'
    # A temporarily hidden status is not evidence that the turn changed.
    if turn is not None and turn != 'you':
        return 'unknown'
    return None


def parse_candidates(text):
    lines = []
    for line in text.splitlines():
        line = re.sub(r'^\s*(?:[-*•]|\d+[.)])\s*', '', line).strip().strip('"\'`')
        if line and len(line) <= 60 and line.casefold() not in {x.casefold() for x in lines}:
            lines.append(line)
    return clean_candidates(lines)


async def generate(client, model, question, used, overlay=False):
    started = time.monotonic()
    instructions = ('Give valid answers for a trivia category. Return only a JSON object with keys ordinary and specific. '
                    'The ordinary array must contain 10 distinct common, familiar answers. '
                    'The specific array must contain 4 distinct answers that are '
                    'less common but clearly correct. Avoid every used answer and duplicates across groups.'
                    if overlay else
                    'Answer a trivia category. Give 8 distinct, valid answers, one per line, no explanations or numbering. Respect every constraint; avoid answers in the used list. Aim for the rarest correct answers that the game is likely to accept. Rank answers from rarest to least rare; never sacrifice correctness for rarity.')
    response = await client.responses.create(
        model=model, reasoning={'effort': 'none'}, max_output_tokens=400 if overlay else 100,
        instructions=instructions,
        input=f'Question: {question}\nAlready used: {", ".join(sorted(used)) or "none"}',
        store=False,
    )
    if overlay:
        try:
            data = json.loads(response.output_text)
            if not isinstance(data, dict) or any(not isinstance(data.get(k), list) for k in ('ordinary', 'specific')):
                raise ValueError('expected ordinary and specific arrays')
            groups = {k: [v for v in data[k] if isinstance(v, str)] for k in ('ordinary', 'specific')}
            return clean_groups(groups, used), time.monotonic() - started
        except (ValueError, TypeError) as exc:
            raise RuntimeError('Model returned invalid grouped suggestions') from exc
    return parse_candidates(response.output_text), time.monotonic() - started


async def read_page(page):
    return await page.evaluate('''() => {
      const visible = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
      const prompts = [...document.querySelectorAll('.ds-card:not(.pf-newcat):not(.gone) .prompt')].filter(visible);
      const status = document.querySelector('.pf-status:not(.gone)');
      const input = document.querySelector('input[aria-label="Your answer"]');
      const reject = document.querySelector('.ds-reject');
      const card = prompts.at(-1)?.closest('.ds-card');
      return {question: prompts.at(-1)?.textContent?.trim() || '',
        category: (card?.querySelector('.rnd span') || card?.querySelector('.rnd'))?.textContent?.trim() || '',
        turn: status?.textContent?.trim() || '',
        placeholder: input?.getAttribute('placeholder') || '',
        input_enabled: !!input && !input.disabled,
        reject: reject && visible(reject) ? reject.textContent.trim() : '',
        answers: [...document.querySelectorAll('.pf-say.on.ok')].filter(visible).map(e => ({text: e.textContent.trim(), own: !!e.closest('.me'), rarity: e.style.getPropertyValue('--cc').match(/--tier-([a-z]+)/)?.[1] || null})).filter(e => e.text)};
    }''')


async def join_ranked(page, name, table_size):
    if name:
        await page.get_by_placeholder('what the ring calls you').fill(name)
    labels = {'1v1': '1V1', '3s': '3S', '4-6': '4–6', '8-10': '8–10'}
    await page.get_by_role('radio', name=labels[table_size], exact=True).check(force=True)
    await page.get_by_role('button', name=re.compile(r'RATED', re.I)).click(force=True)
    log(f'Finding ranked game · {labels[table_size]}', 'info')


async def host_new(page, name):
    await page.get_by_placeholder('what the ring calls you').fill(name)
    privacy = page.locator('button.pf-privacy[aria-pressed]')
    for _ in range(5):
        if await privacy.get_attribute('aria-pressed') == 'true':
            break
        await privacy.click(force=True)
        await page.wait_for_timeout(500)
    if await privacy.get_attribute('aria-pressed') != 'true':
        raise RuntimeError('Could not set the room to private.')
    await page.get_by_placeholder('what the ring calls you').fill(name)
    log('Creating a private room…')
    await page.get_by_role('button', name='HOST A ROOM').click(force=True)
    await page.wait_for_url(re.compile(r'^https://krillion\.io/party/[A-Z]{4}(?:[?#].*)?$'), timeout=30000)
    code = page.url.split('/party/', 1)[1].split('?', 1)[0].split('#', 1)[0]
    log(f'Private room: {code} · https://krillion.io/party/{code}', 'question')


@asynccontextmanager
async def open_game_page(args):
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        if args.ranked:
            profile = Path.home() / '.krillion-bot' / 'firefox-ranked'
            profile.mkdir(parents=True, exist_ok=True)
            context = await playwright.firefox.launch_persistent_context(str(profile), headless=False)
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            browser = await playwright.firefox.launch(headless=False)
            page = await browser.new_page()
        url = f'https://krillion.io/party/{args.code}' if args.code else 'https://krillion.io/party'
        await page.goto(url, wait_until='domcontentloaded')
        if args.ranked:
            await join_ranked(page, args.join_name or 'Krillbot', args.table_size)
        elif args.new:
            await host_new(page, args.join_name or 'Krillbot')
        elif args.join_name and args.code:
            name = page.get_by_placeholder('what the ring calls you')
            await name.wait_for(timeout=15000)
            await name.fill(args.join_name)
            await page.get_by_role('button', name='TAKE A SEAT').click(force=True, timeout=10000)
            log('Requested a seat in the room.')
            await page.wait_for_timeout(2000)
            if await page.get_by_text('This room is full.', exact=True).count():
                raise RuntimeError('This room is full. Free a seat or use a larger room, then try again.')
        if not args.ranked:
            log('Browser opened. Join or host a Puffer Party game in this window. Press Ctrl+C to stop.')
        yield page


async def run(args, overlay=None, stop_event=None):
    from openai import AsyncOpenAI

    if not args.observe and not os.environ.get('OPENAI_API_KEY'):
        raise RuntimeError('Set OPENAI_API_KEY before starting the live bot.')
    client = None if args.observe else AsyncOpenAI(timeout=args.model_timeout, max_retries=0)
    store = Store(args.db)
    async with open_game_page(args) as page:
        question_key = None
        question = ''
        used = set()
        candidates = []
        overlay_candidates = {'ordinary': [], 'specific': []}
        generation = None
        last_turn = None
        last_reject = ''
        refill_requested = False
        pending = None
        attempted = set()
        seen_answers = set()
        previous_overlay = None
        model_error = None
        while not page.is_closed() and not (stop_event and stop_event.is_set()):
            try:
                state = await read_page(page)
            except Exception as exc:
                log(f'Waiting for page: {exc}', 'error')
                await asyncio.sleep(0.5)
                continue
            q = state['question']
            key = (state['category'], q)
            if q and key != question_key:
                if pending:
                    log(f'{pending} · result unknown', 'result')
                    pending = None
                if generation and not generation.done():
                    generation.cancel()
                question_key, question = key, q
                used, attempted, seen_answers = set(), set(), set()
                refill_requested = False
                model_error = None
                candidates = []
                overlay_candidates = {'ordinary': [], 'specific': []}
                last_turn, last_reject = None, ''
                log(f'{state["category"]}  {question}', 'question')
                for group in store.lookup(question, 'puffer-party'):
                    decisive = next((r for r in group if r['status'] in ('accepted', 'rejected')), None)
                    if decisive and decisive['status'] == 'accepted':
                        candidates.append(decisive['answer'])
                        if overlay:
                            tier = next((r['rarity'] for r in group if r['rarity'] and r['status'] in ('accepted', 'observed')), None)
                            category = ('ordinary' if tier in ('plankton', 'schooler') else
                                        'specific' if tier in ('rare', 'deepcut', 'krillion') else None)
                            if category:
                                overlay_candidates[category].append(decisive['answer'])
                if not args.observe:
                    generation = asyncio.create_task(generate(client, args.model, question, used, overlay=bool(overlay)))
            for observed in state['answers'] if question else []:
                answer = observed['text']
                key_answer = answer_key(answer)
                if key_answer and key_answer not in seen_answers:
                    seen_answers.add(key_answer)
                    used.add(answer)
                    candidates = clean_candidates(candidates, used | attempted)
                    if observed['own']:
                        store.record(question, 'puffer-party', answer, 'accepted', 'visible own answer bubble after pass', rarity=observed['rarity'])
                        log(f'{answer} · accepted', 'sent')
                        if pending and answer_key(pending) == key_answer:
                            pending = None
                    else:
                        store.record(question, 'puffer-party', answer, 'observed', 'visible answer bubble after pass', rarity=observed['rarity'])
                        log(f'played  →  {answer}', 'turn')
            turn = current_turn(state)
            feedback = state['reject']
            result = pending_result(pending, feedback, turn)
            if feedback and feedback != last_reject:
                log(feedback, 'result')
                if overlay and not pending:
                    match = re.match(r'^[“\"](.+?)[”\"]:', feedback)
                    if match:
                        rejected_answer = match.group(1)
                        used.add(rejected_answer)
                        if 'no echo' in feedback.lower():
                            store.record(question, 'puffer-party', rejected_answer, 'rejected', 'visible game feedback: ' + feedback)
                last_reject = feedback
            elif not feedback:
                last_reject = ''
            if result in ('rejected', 'repeat'):
                if result == 'rejected':
                    store.record(question, 'puffer-party', pending, 'rejected', 'visible game feedback: ' + feedback)
                used.add(pending)
                pending = None
            elif result == 'unknown':
                log(f'{pending} · result unknown', 'result')
                pending = None
            if turn != last_turn:
                if turn and turn != 'you':
                    log(f'{turn} is up', 'turn')
                refill_requested = False
                last_turn = turn
            if overlay and overlay.regenerate.is_set():
                overlay.regenerate.clear()
                if question:
                    if generation and not generation.done():
                        generation.cancel()
                    previous = overlay_candidates['ordinary'] + overlay_candidates['specific']
                    excluded = used | attempted | set(previous)
                    overlay_candidates = {'ordinary': [], 'specific': []}
                    model_error = None
                    refill_requested = True
                    generation = asyncio.create_task(generate(client, args.model, question, excluded, overlay=True))
            if generation and generation.done():
                try:
                    generated, elapsed = generation.result()
                    model_error = None
                    generated_answers = (generated['ordinary'] + generated['specific']) if overlay else generated
                    for answer in generated_answers:
                        store.record(question, 'puffer-party', answer, 'suggested', f'OpenAI model {args.model}')
                    if overlay:
                        for category in ('ordinary', 'specific'):
                            overlay_candidates[category].extend(generated[category])
                        overlay_candidates = clean_groups(overlay_candidates, used | attempted)
                    else:
                        candidates = clean_candidates(candidates + generated, used | attempted)
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    model_error = str(exc)
                    log(f'Model error: {exc}', 'error')
                generation = None
            if not args.observe and question and turn == 'you' and state['input_enabled'] and not pending:
                candidates = clean_candidates(candidates, used | attempted)
                answer = candidates[0] if candidates and not overlay else None
                if overlay:
                    overlay_candidates = clean_groups(overlay_candidates, used | attempted)
                    if overlay.autoplay.is_set():
                        options = overlay_candidates['specific'] + overlay_candidates['ordinary']
                        answer = options[0] if options else None
                needs_more = (any(len(overlay_candidates[k]) < limit for k, limit in OVERLAY_COUNTS.items()) if overlay else not answer)
                if needs_more and not generation and not refill_requested:
                    refill_requested = True
                    generation = asyncio.create_task(generate(client, args.model, question, used | attempted, overlay=bool(overlay)))
                if answer and (not overlay or overlay.autoplay.is_set()):
                    # Check again immediately before sending, since a model request may finish after the turn ends.
                    fresh = await read_page(page)
                    if fresh['question'] == question and fresh['category'] == state['category'] and current_turn(fresh) == 'you' and fresh['input_enabled']:
                        attempted.add(answer)
                        candidates = clean_candidates(candidates, used | attempted)
                        field = page.locator('input[aria-label="Your answer"]')
                        await field.fill(answer)
                        fresh = await read_page(page)
                        if current_turn(fresh) == 'you' and fresh['question'] == question and (not overlay or overlay.autoplay.is_set()):
                            await field.press('Enter')
                            pending = answer
                            log(f'you  →  {answer}', 'sent')
                        else:
                            await field.fill('')
                            log('Turn or mode changed before submission; skipped.', 'result')
            if overlay:
                overlay_candidates = clean_groups(overlay_candidates, used | attempted)
                visible_groups = {key: values[:OVERLAY_COUNTS[key]] for key, values in overlay_candidates.items()}
                snapshot = (question, turn, tuple(visible_groups['ordinary']), tuple(visible_groups['specific']), bool(generation), model_error)
                if snapshot != previous_overlay:
                    overlay.publish(question, turn, visible_groups, bool(generation), model_error)
                    previous_overlay = snapshot
            await asyncio.sleep(args.poll)
        if generation and not generation.done():
            generation.cancel()
        if client:
            await client.close()
