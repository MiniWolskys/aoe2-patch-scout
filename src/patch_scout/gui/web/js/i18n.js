// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * Look up user-visible text by key, with named placeholders (D-36).
 *
 * Same rules as the Python catalog: `{name}` is replaced by its value, and `{{` and `}}` are
 * literal braces. Anything else between braces throws, as do a missing key or value.
 */

const PLACEHOLDER_NAME = /^[A-Za-z_][A-Za-z0-9_]*$/;

/**
 * Fill a template's named placeholders.
 * @param {string} template
 * @param {Record<string, unknown>} values
 * @returns {string}
 */
export function format(template, values) {
  let result = "";
  let index = 0;
  while (index < template.length) {
    const char = template[index];
    const next = template[index + 1];
    if ((char === "{" || char === "}") && next === char) {
      result += char;
      index += 2;
    } else if (char === "{") {
      const end = template.indexOf("}", index);
      if (end === -1) {
        throw new Error(`unclosed "{" in ${JSON.stringify(template)}`);
      }
      const name = template.slice(index + 1, end);
      if (!PLACEHOLDER_NAME.test(name)) {
        throw new Error(`{${name}} isn't a plain placeholder name`);
      }
      if (!Object.hasOwn(values, name)) {
        throw new Error(`no value for {${name}}`);
      }
      result += String(values[name]);
      index = end + 1;
    } else if (char === "}") {
      throw new Error(`single "}" in ${JSON.stringify(template)}`);
    } else {
      result += char;
      index += 1;
    }
  }
  return result;
}

/**
 * Create the text lookup for a set of resolved messages.
 * @param {Record<string, string>} messages Messages with the English fallback already applied.
 * @returns {(key: string, values?: Record<string, unknown>) => string}
 */
export function createTranslator(messages) {
  return (key, values = {}) => {
    if (!Object.hasOwn(messages, key)) {
      throw new Error(`no message for key ${JSON.stringify(key)}`);
    }
    try {
      return format(messages[key], values);
    } catch (error) {
      throw new Error(`message ${JSON.stringify(key)}: ${error.message}`, { cause: error });
    }
  };
}

/**
 * Fill in `data-i18n` text and `data-i18n-attr` attributes under `root`.
 * `data-i18n-attr` holds space-separated `attribute:key` pairs.
 * @param {ParentNode} root
 * @param {(key: string) => string} t
 */
export function applyTranslations(root, t) {
  for (const element of root.querySelectorAll("[data-i18n]")) {
    element.textContent = t(element.dataset.i18n);
  }
  for (const element of root.querySelectorAll("[data-i18n-attr]")) {
    for (const pair of element.dataset.i18nAttr.trim().split(/\s+/)) {
      const [attribute, key] = pair.split(":");
      element.setAttribute(attribute, t(key));
    }
  }
}
