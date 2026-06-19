"""Browser integration tests for Family Blackjack frontend using Playwright."""

from playwright.sync_api import Page, expect

def test_lobby_join(live_server, page: Page):
    """Test that a player can join the lobby and appears in the players list."""
    page.goto(live_server)

    # Verify setup panel is initially visible
    expect(page.locator("#setup-panel")).to_be_visible()

    # Enter username and join
    page.fill("#username", "Alice")
    page.click("#join-btn")

    # Verify setup panel is hidden after joining
    expect(page.locator("#setup-panel")).to_be_hidden()

    # Verify username is displayed in the active players list
    expect(page.locator("#player-list-box")).to_contain_text("Alice")

def test_invalid_username_validation(live_server, page: Page):
    """Test that invalid usernames are rejected by the backend validation."""
    page.goto(live_server)

    # Enter an invalid name containing HTML tags
    page.fill("#username", "Alice<script>")
    page.click("#join-btn")

    # Setup panel should remain visible due to rejection
    expect(page.locator("#setup-panel")).to_be_visible()

    # Toast notification should display the error message
    expect(page.locator("#toast-notification")).to_be_visible()
    expect(page.locator("#toast-notification")).to_contain_text("Name must be 1-20 characters")

def test_add_bot(live_server, page: Page):
    """Test that a player can add a bot to the lobby."""
    page.goto(live_server)

    # Join the lobby first
    page.fill("#username", "Bob")
    page.click("#join-btn")

    # Verify lobby controls are visible
    expect(page.locator("#lobby-controls")).to_be_visible()

    # Add a bot
    page.click("#add-bot-btn")

    # Verify player list contains the bot emoji prefix
    expect(page.locator("#player-list-box")).to_contain_text("🤖")
