// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * The image export (P-13): the page on screen drawn as PNG images for a video, 1920 px wide and
 * at most 1080 px tall each, so a long page comes out in parts. Drawn on a canvas from the
 * comparison's own data, with the app's fonts and colours; no screenshot library.
 */

import { scopeText } from "./comparison.js";
import { message } from "./i18n.js";
import * as icons from "./icons.js";

export const WIDTH = 1920;
export const HEIGHT = 1080;
const MARGIN = 72;
const HEADER = 150;
const FOOTER = 64;
const FONT = "'Barlow Semi Condensed', 'Segoe UI', sans-serif";
const COLOURS = {
  background: "#15120f",
  line: "#241f19",
  text: "#ece3d3",
  text2: "#aa9e8a",
  text3: "#8a7f6d",
  accent: "#c9a45c",
  old: "#e35b50",
  new: "#92dcaa",
};
// Columns, in px from the left.
const ICON = { x: MARGIN, size: 56 };
const NAME = { x: MARGIN + 76, width: 520 };
const FIELD = { x: 690, width: 380 };
// Values may be words ("Needs a prerequisite"), so each side gets about 230 px.
const VALUES = { oldRight: 1310, width: 230, arrow: 1326, newLeft: 1356 };
const SCOPE = { x: 1610, width: WIDTH - MARGIN - 1610 };
const LINE = 34;
const CATEGORY = 52;

/**
 * Draw a page as one or more PNG images.
 * @param {{
 *   page: {title: string, categories: Array<{title: string, entries: Array<Record<string, any>>}>},
 *   versions: string,
 *   notice: string,
 *   t: (key: string, values?: Record<string, unknown>) => string,
 * }} input
 * @returns {Promise<string[]>} PNG data URLs, one per part
 */
export async function draw(input) {
  await Promise.all(
    ["400", "600"].map((weight) => document.fonts.load(`${weight} 24px 'Barlow Semi Condensed'`)),
  );
  const images = await loadIcons(input.page);
  const measure = context(document.createElement("canvas"));
  const blocks = layout(measure, input);
  const parts = paginate(blocks);
  return parts.map((part, index) => {
    const canvas = document.createElement("canvas");
    canvas.width = WIDTH;
    canvas.height = HEIGHT;
    const ctx = context(canvas);
    ctx.fillStyle = COLOURS.background;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    header(ctx, input, parts.length > 1 ? ` (${index + 1}/${parts.length})` : "");
    let y = HEADER;
    for (const block of part) {
      block.draw(ctx, y, images);
      y += block.height;
    }
    footer(ctx, input.notice);
    return canvas.toDataURL("image/png");
  });
}

/**
 * @param {HTMLCanvasElement} canvas
 * @returns {CanvasRenderingContext2D}
 */
function context(canvas) {
  const ctx = canvas.getContext("2d");
  if (ctx === null) {
    throw new Error("no 2D canvas");
  }
  ctx.textBaseline = "alphabetic";
  return ctx;
}

/**
 * Every icon the page shows, decoded, by hash.
 * @param {{categories: Array<{entries: Array<Record<string, any>>}>}} page
 * @returns {Promise<Map<string, HTMLImageElement>>}
 */
async function loadIcons(page) {
  const found = new Map();
  const hashes = new Set();
  for (const group of page.categories) {
    for (const entry of group.entries) {
      if (entry.entity?.icon?.hash) {
        hashes.add(entry.entity.icon.hash);
      }
    }
  }
  await Promise.all(
    [...hashes].map(async (hash) => {
      const source = icons.source(hash);
      if (source === undefined) {
        return;
      }
      const image = new Image();
      image.src = source;
      try {
        await image.decode();
        found.set(hash, image);
      } catch {
        // An icon that can't be decoded is left out, like on screen.
      }
    }),
  );
  return found;
}

/**
 * @typedef {{height: number, keepWithNext?: boolean,
 *   draw: (ctx: CanvasRenderingContext2D, y: number, images: Map<string, HTMLImageElement>) => void}} Block
 */

/**
 * The page as blocks of known height: category headings and entries.
 * @param {CanvasRenderingContext2D} ctx
 * @param {Parameters<typeof draw>[0]} input
 * @returns {Block[]}
 */
function layout(ctx, input) {
  /** @type {Block[]} */
  const blocks = [];
  if (input.page.categories.length === 0) {
    blocks.push({
      height: CATEGORY,
      draw: (c, y) => text(c, input.t("comparison.no_changes"), MARGIN, y + 34, 24, COLOURS.text2),
    });
  }
  for (const group of input.page.categories) {
    blocks.push({
      height: CATEGORY,
      keepWithNext: true,
      draw: (c, y) =>
        text(c, group.title.toUpperCase(), MARGIN, y + 36, 18, COLOURS.text3, "600", 1.5),
    });
    for (const entry of group.entries) {
      blocks.push(entryBlock(ctx, entry, input.t));
    }
  }
  return blocks;
}

/**
 * One entry: icon, name, one line per change, and its civs.
 * @param {CanvasRenderingContext2D} ctx
 * @param {Record<string, any>} entry
 * @param {(key: string, values?: Record<string, unknown>) => string} t
 * @returns {Block}
 */
function entryBlock(ctx, entry, t) {
  const kind = entry.kind === "added" || entry.kind === "removed" ? t(`kind.${entry.kind}`) : "";
  const name = `${kind ? `${kind} ` : ""}${entry.entity?.name ?? ""}`;
  const nameLines = wrap(ctx, name, NAME.width, 26, "600").slice(0, 2);
  const where = entry.entity?.where ?? "";
  // Every civ by name, as in the other exports: nothing may be cut (diff-rules.md).
  const scope = wrap(ctx, scopeText(t, entry.scope, Infinity), SCOPE.width, 18, "400");
  const lines = (entry.changes ?? []).map((change) => changeLines(ctx, change, t));
  const linesHeight = lines.reduce((sum, line) => sum + line.height, 0);
  const nameHeight = nameLines.length * 32 + (where ? 26 : 0);
  const height = Math.max(
    ICON.size + 24,
    linesHeight + 24,
    nameHeight + 24,
    scope.length * 24 + 24,
  );
  return {
    height,
    draw: (c, y, images) => {
      c.fillStyle = COLOURS.line;
      c.fillRect(MARGIN, y + height - 1, WIDTH - 2 * MARGIN, 1);
      const image = images.get(entry.entity?.icon?.hash);
      if (image) {
        c.drawImage(image, ICON.x, y + 12, ICON.size, ICON.size);
      }
      nameLines.forEach((line, index) => {
        text(c, line, NAME.x, y + 40 + index * 32, 26, COLOURS.text, "600");
      });
      if (where) {
        text(c, where, NAME.x, y + 40 + nameLines.length * 32 - 6, 18, COLOURS.text3);
      }
      scope.forEach((line, index) => {
        text(c, line, SCOPE.x, y + 38 + index * 24, 18, COLOURS.text3);
      });
      let lineY = y + 12;
      for (const line of lines) {
        line.draw(c, lineY);
        lineY += line.height;
      }
    },
  };
}

/**
 * One change: its field and old → new values, or a word diff for a text change.
 * @param {CanvasRenderingContext2D} ctx
 * @param {Record<string, any>} change
 * @param {(key: string, values?: Record<string, unknown>) => string} t
 * @returns {{height: number, draw: (ctx: CanvasRenderingContext2D, y: number) => void}}
 */
function changeLines(ctx, change, t) {
  const field = change.field ? message(t, change.field.key, change.field.args) : "";
  const words = change.words ?? [];
  if (words.length > 0) {
    const runs = layoutWords(ctx, words, WIDTH - MARGIN - FIELD.x - SCOPE.width - 40);
    return {
      height: LINE + runs.lines * 30,
      draw: (c, y) => {
        text(c, field, FIELD.x, y + 26, 22, COLOURS.text2);
        for (const run of runs.items) {
          const colour =
            run.kind === "removed"
              ? COLOURS.old
              : run.kind === "added"
                ? COLOURS.new
                : COLOURS.text;
          text(c, run.text, FIELD.x + run.x, y + LINE + 22 + run.line * 30, 22, colour);
          if (run.kind === "removed") {
            c.fillStyle = COLOURS.old;
            c.fillRect(FIELD.x + run.x, y + LINE + 14 + run.line * 30, run.width, 2);
          }
        }
      },
    };
  }
  const fieldLines = wrap(ctx, field, FIELD.width, 22, "400").slice(0, 2);
  return {
    height: Math.max(1, fieldLines.length) * LINE,
    draw: (c, y) => {
      fieldLines.forEach((line, index) => {
        text(c, line, FIELD.x, y + 26 + index * LINE, 22, COLOURS.text2);
      });
      const old = change.old ?? "";
      const now = change.new ?? "";
      if (old) {
        c.textAlign = "right";
        value(c, old, VALUES.oldRight, y + 26, COLOURS.old);
        c.textAlign = "left";
      }
      if (old && now) {
        text(c, "→", VALUES.arrow, y + 26, 26, COLOURS.text3);
      }
      if (now) {
        value(c, now, VALUES.newLeft, y + 26, COLOURS.new);
      }
    },
  };
}

/**
 * Lay a word diff out in lines.
 * @param {CanvasRenderingContext2D} ctx
 * @param {Array<{kind: string, text: string}>} words
 * @param {number} width
 * @returns {{lines: number, items: Array<{kind: string, text: string, x: number, width: number, line: number}>}}
 */
function layoutWords(ctx, words, width) {
  ctx.font = `400 22px ${FONT}`;
  const items = [];
  let x = 0;
  let line = 0;
  for (const word of words) {
    for (const token of word.text.split(/(\s+)/)) {
      if (token === "") {
        continue;
      }
      if (token.includes("\n")) {
        // A blank line between two parts of a civ bonus list stays blank.
        x = 0;
        line += token.split("\n").length - 1;
        continue;
      }
      const tokenWidth = ctx.measureText(token).width;
      if (x + tokenWidth > width && x > 0 && token.trim() !== "") {
        x = 0;
        line += 1;
      }
      if (x === 0 && token.trim() === "") {
        continue;
      }
      items.push({ kind: word.kind, text: token, x, width: tokenWidth, line });
      x += tokenWidth;
    }
  }
  return { lines: line + 1, items };
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {Parameters<typeof draw>[0]} input
 * @param {string} part
 */
function header(ctx, input, part) {
  text(ctx, input.t("app.title").toUpperCase(), MARGIN, 58, 18, COLOURS.accent, "600", 2);
  text(ctx, `${input.page.title}${part}`, MARGIN, 112, 48, COLOURS.text, "600");
  ctx.textAlign = "right";
  text(ctx, fit(ctx, input.versions, 900, 22, "400"), WIDTH - MARGIN, 112, 22, COLOURS.text2);
  ctx.textAlign = "left";
  ctx.fillStyle = COLOURS.line;
  ctx.fillRect(MARGIN, HEADER - 12, WIDTH - 2 * MARGIN, 2);
}

/**
 * The Microsoft notice exports carry (legal.md).
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} notice
 */
function footer(ctx, notice) {
  const lines = wrap(ctx, notice, WIDTH - 2 * MARGIN, 14, "400").slice(0, 2);
  lines.forEach((line, index) => {
    text(ctx, line, MARGIN, HEIGHT - FOOTER + 26 + index * 18, 14, COLOURS.text3);
  });
}

/**
 * Split blocks into parts that fit a 1080 px image; a heading never ends a part.
 * @param {Block[]} blocks
 * @returns {Block[][]}
 */
function paginate(blocks) {
  const room = HEIGHT - HEADER - FOOTER;
  /** @type {Block[][]} */
  const parts = [[]];
  let used = 0;
  blocks.forEach((block, index) => {
    const next = blocks[index + 1];
    const needed = block.height + (block.keepWithNext && next ? next.height : 0);
    if (used > 0 && used + needed > room) {
      parts.push([]);
      used = 0;
    }
    parts[parts.length - 1].push(block);
    used += block.height;
  });
  return parts;
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} value
 * @param {number} x
 * @param {number} y
 * @param {number} size
 * @param {string} colour
 * @param {string} [weight]
 * @param {number} [spacing]
 */
function text(ctx, value, x, y, size, colour, weight = "400", spacing = 0) {
  ctx.font = `${weight} ${size}px ${FONT}`;
  ctx.fillStyle = colour;
  ctx.letterSpacing = `${spacing}px`;
  ctx.fillText(value, x, y);
  ctx.letterSpacing = "0px";
}

/**
 * Break a text into lines no wider than `width`.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} value
 * @param {number} width
 * @param {number} size
 * @param {string} weight
 * @returns {string[]}
 */
function wrap(ctx, value, width, size, weight) {
  ctx.font = `${weight} ${size}px ${FONT}`;
  const lines = [];
  let current = "";
  for (const word of value.split(/\s+/).filter((part) => part !== "")) {
    const candidate = current ? `${current} ${word}` : word;
    if (current && ctx.measureText(candidate).width > width) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) {
    lines.push(current);
  }
  return lines;
}

/**
 * One old or new value: smaller type for a long one, an ellipsis only as a last resort.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} raw
 * @param {number} x
 * @param {number} y
 * @param {string} colour
 */
function value(ctx, raw, x, y, colour) {
  for (const size of [26, 22, 18]) {
    ctx.font = `600 ${size}px ${FONT}`;
    if (ctx.measureText(raw).width <= VALUES.width || size === 18) {
      text(ctx, fit(ctx, raw, VALUES.width, size, "600"), x, y, size, colour, "600");
      return;
    }
  }
}

/**
 * A value cut with an ellipsis when it is wider than `width`.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} value
 * @param {number} width
 * @param {number} size
 * @param {string} weight
 * @returns {string}
 */
function fit(ctx, value, width, size, weight) {
  ctx.font = `${weight} ${size}px ${FONT}`;
  if (ctx.measureText(value).width <= width) {
    return value;
  }
  let cut = value;
  while (cut.length > 1 && ctx.measureText(`${cut}…`).width > width) {
    cut = cut.slice(0, -1);
  }
  return `${cut}…`;
}
