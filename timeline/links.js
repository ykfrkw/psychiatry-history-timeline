/*
 * Purpose: 項目をクリックすると Wikipedia／Amazon（書籍）／PubMed（論文）の検索リンクを小さなメニューで出す
 * Inputs:  render.py が先頭に差し込む LINKS（id → {n: 見出し, w: Wikipedia 検索語, a: Amazon 検索語, p: PubMed 検索語}）と
 *          AMAZON_TAG（アソシエイトのタグ。空なら Amazon リンクにタグを付けない）
 * Outputs: [data-id] 要素に .has-lk を付け、クリックで .lk-menu を表示（印刷では CSS で隠す）
 * Depends: なし
 */
(() => {
  const MENU_MARGIN_PX = 8;
  const CURSOR_OFFSET_PX = 6;
  const enc = encodeURIComponent;

  const linkTargets = (entry) => {
    const targets = [];
    if (entry.a) {
      const tag = AMAZON_TAG ? `&tag=${enc(AMAZON_TAG)}` : "";
      targets.push(["Amazon", "書籍", `https://www.amazon.co.jp/s?k=${enc(entry.a)}${tag}`]);
    }
    if (entry.w) targets.push(["Wikipedia", "", `https://ja.wikipedia.org/w/index.php?search=${enc(entry.w)}`]);
    if (entry.p) targets.push(["PubMed", "論文", `https://pubmed.ncbi.nlm.nih.gov/?term=${enc(entry.p)}`]);
    return targets;
  };

  for (const el of document.querySelectorAll("[data-id]")) {
    const entry = LINKS[el.dataset.id];
    if (entry && linkTargets(entry).length) el.classList.add("has-lk");
  }

  let menu = null;
  const closeMenu = () => {
    if (!menu) return;
    menu.remove();
    menu = null;
  };

  const buildMenu = (entry) => {
    const box = document.createElement("div");
    box.className = "lk-menu";
    const head = document.createElement("div");
    head.className = "lk-h";
    head.textContent = entry.n;
    box.appendChild(head);
    for (const [label, note, href] of linkTargets(entry)) {
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.target = "_blank";
      // アフィリエイトを含むので sponsored を付ける
      anchor.rel = "noopener sponsored";
      anchor.textContent = label;
      if (note) {
        const small = document.createElement("small");
        small.textContent = note;
        anchor.appendChild(small);
      }
      anchor.addEventListener("click", () => setTimeout(closeMenu, 0));
      box.appendChild(anchor);
    }
    return box;
  };

  const placeMenu = (box, event) => {
    const rect = box.getBoundingClientRect();
    let x = event.clientX + CURSOR_OFFSET_PX;
    let y = event.clientY + CURSOR_OFFSET_PX;
    if (x + rect.width > innerWidth - MENU_MARGIN_PX) x = innerWidth - rect.width - MENU_MARGIN_PX;
    if (y + rect.height > innerHeight - MENU_MARGIN_PX) y = event.clientY - rect.height - CURSOR_OFFSET_PX;
    box.style.left = `${Math.max(MENU_MARGIN_PX, x)}px`;
    box.style.top = `${Math.max(MENU_MARGIN_PX, y)}px`;
  };

  document.addEventListener("click", (event) => {
    if (menu && menu.contains(event.target)) return;
    const item = event.target.closest(".has-lk");
    closeMenu();
    if (!item) return;
    menu = buildMenu(LINKS[item.dataset.id]);
    document.body.appendChild(menu);
    placeMenu(menu, event);
    event.stopPropagation();
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeMenu(); });
  addEventListener("scroll", closeMenu, true);
})();
