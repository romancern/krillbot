import unittest

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None
from krillion.live import host_new, join_ranked, read_page, parse_turn


@unittest.skipUnless(async_playwright, 'Playwright not installed')
class BrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_visible_game_state(self):
        async with async_playwright() as p:
            browser = await p.firefox.launch()
            page = await browser.new_page()
            await page.set_content('''<div class="ds-card ds-px pf-newcat"><div class="prompt">New category</div></div>
              <div class="ds-card ds-px"><div class="rnd"><span>CATEGORY 1</span><span>NEW</span></div><div class="prompt">Name a fruit</div></div>
              <div class="pf-status">▸ <b>your puffer</b> · type an answer</div>
              <input aria-label="Your answer" placeholder="your puffer — type!">
              <div class="pf-say on ok" style="--cc: var(--tier-rare, red)">Apple</div><div class="pf-say on caret">typing</div>
              <div class="ds-reject">“pear”: no echo. keep going</div>''')
            state = await read_page(page)
            self.assertEqual(state['question'], 'Name a fruit')
            self.assertEqual(state['category'], 'CATEGORY 1')
            self.assertEqual(parse_turn(state['turn']), 'you')
            self.assertIn('no echo', state['reject'])
            self.assertTrue(state['input_enabled'])
            self.assertEqual(state['answers'], [{'text': 'Apple', 'own': False, 'rarity': 'rare'}])
            await browser.close()

    async def test_ranked_lobby_selection(self):
        async with async_playwright() as p:
            browser = await p.firefox.launch()
            page = await browser.new_page()
            await page.set_content('''<input placeholder="what the ring calls you">
                <label><input type="radio" name="size">1V1</label>
                <label><input type="radio" name="size">4–6</label>
                <button onclick="this.dataset.clicked='yes'">▶ RATED ◀</button>''')
            await join_ranked(page, 'Krillbot', '1v1')
            self.assertEqual(await page.get_by_placeholder('what the ring calls you').input_value(), 'Krillbot')
            self.assertTrue(await page.get_by_role('radio', name='1V1').is_checked())
            self.assertEqual(await page.get_by_role('button', name='▶ RATED ◀').get_attribute('data-clicked'), 'yes')
            await browser.close()

    async def test_host_new_chooses_private_before_hosting(self):
        async with async_playwright() as p:
            browser = await p.firefox.launch()
            page = await browser.new_page()
            async def respond(route):
                if route.request.url.endswith('/party'):
                    await route.fulfill(content_type='text/html', body="""<input placeholder='what the ring calls you'>
                      <button class='pf-privacy' aria-pressed='false' onclick="this.setAttribute('aria-pressed','true')">PUBLIC</button>
                      <button class='pf-privacy pf-load-more'>LOAD MORE</button>
                      <button onclick="if(document.querySelector('[aria-pressed]').getAttribute('aria-pressed')==='true') location.href='/party/ABCD'">HOST A ROOM</button>""")
                else:
                    await route.fulfill(content_type='text/html', body='private room')
            await page.route('https://krillion.io/**', respond)
            await page.goto('https://krillion.io/party')
            await host_new(page, 'Krillbot')
            self.assertEqual(page.url, 'https://krillion.io/party/ABCD')
            await browser.close()
