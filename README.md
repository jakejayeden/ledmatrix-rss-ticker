# LEDMatrix RSS News Ticker

A third-party plugin for [ChuckBuilds/LEDMatrix](https://github.com/ChuckBuilds/LEDMatrix) that displays RSS/Atom news headlines as a scrolling ticker.

Designed around a 128x32 LED matrix, while reading the actual display size at runtime so it can adapt to other panel sizes.

## Features

- Multiple RSS or Atom feeds
- Feed editor directly in the LEDMatrix WebUI
- Per-feed custom logo upload
- Per-feed headline colour
- Fixed logo on the left with scrolling text to the right
- Configurable headlines per feed
- Round-robin feed rotation
- Remembers each feed's position, so the next visit shows the next group of headlines
- Configurable ticker speed and headline spacing
- Configurable RSS refresh interval
- Dynamic-duration support so LEDMatrix can wait for a feed cycle to complete
- Falls back to the feed name when no logo is configured

## Example rotation

With `headlines_per_feed` set to `3`:

1. BBC headlines 1-3
2. Reuters headlines 1-3
3. BBC headlines 4-6
4. Reuters headlines 4-6
5. Continue through each feed and wrap when required

The logo remains static while the current batch of headlines scrolls through the ticker area.

## Installation

### Development install

From your LEDMatrix checkout:

```bash
./scripts/dev/dev_plugin_setup.sh link-github rss-ticker https://github.com/jakejayeden/ledmatrix-rss-ticker.git
```

If your LEDMatrix configuration is using the production default `plugin-repos` directory, either install/copy the plugin there or temporarily set `plugin_system.plugins_directory` to `plugins` while developing.

### Manual install

Clone the repository into the directory configured by LEDMatrix as `plugin_system.plugins_directory` (normally `plugin-repos`):

```bash
cd /path/to/LEDMatrix/plugin-repos
git clone https://github.com/jakejayeden/ledmatrix-rss-ticker.git rss-ticker
```

Install the dependencies using the same Python environment that runs LEDMatrix:

```bash
pip install -r plugin-repos/rss-ticker/requirements.txt
```

Restart LEDMatrix after the initial plugin installation so it is discovered and loaded.

## WebUI configuration

Open the **RSS News Ticker** plugin configuration page.

The **Feeds** field is an editable table. Add one row per news source and configure:

- **Enabled** - include/exclude the feed
- **Name** - short source name, also used as a fallback when there is no logo
- **RSS URL** - RSS or Atom feed URL
- **Logo** - upload a PNG, JPEG, BMP, or GIF
- **Text colour** - colour used for that feed's headlines

Other settings:

| Setting | Default | Purpose |
|---|---:|---|
| Headlines per feed | 3 | Number of headlines included before moving to the next feed |
| Feed rotation seconds | 30 | Maximum time a feed batch stays active |
| Scroll speed | 30 px/s | Horizontal ticker speed |
| Headline gap | 18 px | Approximate space between headlines |
| Logo width | 28 px | Width reserved for the static logo |
| RSS refresh | 300 s | How often feeds are downloaded |
| Max headlines/feed | 50 | Maximum cached entries for each source |

Changes saved through the WebUI are applied by the plugin without requiring a restart.

## Example configuration

```json
{
  "feeds": [
    {
      "enabled": true,
      "name": "BBC",
      "url": "https://feeds.bbci.co.uk/news/rss.xml",
      "logo": "assets/plugins/rss-ticker/uploads/bbc.png",
      "text_color": [255, 255, 255]
    }
  ],
  "headlines_per_feed": 3,
  "feed_rotation_seconds": 30,
  "rss_refresh_seconds": 300,
  "scroll_speed_px_per_second": 30,
  "headline_gap_px": 18,
  "logo_width": 28
}
```

## Display layout

On a 128x32 panel the default layout reserves 28 pixels on the left for the current feed logo. The remaining width is a clipped ticker viewport.

```text
+------------------------------ 128 px -------------------------------+
|  static logo  |       headline text scrolls right -> left          |
|     28 px     |                                                     |
+---------------------------------------------------------------------+
                              32 px high
```

The scrolling text is rendered into its own viewport before being composited onto the frame, so it cannot draw over the static logo area.

## Feed behaviour

Each feed has an independent cursor. If a feed contains 12 headlines and the batch size is 3, its successive turns start at 1, 4, 7, 10 and then wrap back to 1. Adding other feeds does not reset that position.

Feeds are refreshed independently of the display animation. If a refresh fails, the plugin keeps the previously cached headlines when available.

## Logo behaviour

Uploaded WebUI images are stored by LEDMatrix under its plugin asset area. The plugin also understands an HTTP/HTTPS logo URL if one is placed in the configuration manually.

Logos are resized proportionally to fit inside the configured logo area. Transparent PNGs are supported.

## Requirements

- LEDMatrix >= 2.0.0
- Python packages:
  - `feedparser`
  - `Pillow`
  - `requests`

## Current status

This is an initial `0.1.0` release. The core RSS queue, feed rotation, ticker renderer and WebUI feed editor are implemented. Hardware testing on a real 128x32 matrix is recommended before treating the animation timings as final.

## Repository

https://github.com/jakejayeden/ledmatrix-rss-ticker
