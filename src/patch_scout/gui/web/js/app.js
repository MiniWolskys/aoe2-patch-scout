// SPDX-License-Identifier: GPL-3.0-or-later
/** Start the page: load the startup data, fill in the text, show the right view. */

import { connect } from "./api.js";
import { applyTranslations, createTranslator } from "./i18n.js";
import { initVersionList } from "./version-list.js";

async function start() {
  const api = await connect();
  const startup = await api.get_startup();
  document.documentElement.lang = startup.language;
  const t = createTranslator(startup.messages);
  applyTranslations(document, t);
  initVersionList(document.getElementById("version-list"), { t, versions: startup.versions });
  document.getElementById("first-launch").hidden = startup.versions.length > 0;
  document.body.dataset.ready = "";
}

start().catch((error) => {
  console.error("Patch Scout couldn't start the page", error);
});
