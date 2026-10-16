/*
 * Purpose: 項目にマウスを乗せる（タッチ端末ではタップする）と、見出し・説明と Amazon（書籍）／Wikipedia／PubMed（論文）の
 *          検索リンクを 1 つのメニューにまとめて出す
 * Inputs:  render.py が先頭に差し込む LINKS（id → {n: 見出し, w: Wikipedia 検索語, a: Amazon 検索語, p: PubMed 検索語}）と
 *          AMAZON_TAG（アソシエイトのタグ。空なら Amazon リンクにタグを付けない）。
 *          項目の title 属性（spread.py / render.py が付ける「説明 / 人物 / 出典」）
 * Outputs: リンクのある [data-id] 要素に .has-lk を付け、title を data-tip に移す（ネイティブのツールチップと二重に出さないため）。
 *          ホバー／クリック／タップで .lk-menu を表示（印刷では CSS で隠す）
 * Depends: なし
 */
(() => {
  const MENU_MARGIN_PX = 8;
  const ANCHOR_GAP_PX = 4;
  const HOVER_OPEN_DELAY_MS = 120;
  const HOVER_CLOSE_GRACE_MS = 250;
  const NO_HOVER_QUERY = matchMedia("(hover: none)");
  const enc = encodeURIComponent;

  const linkTargets = (entry) => {
    const targets = [];
    if (entry.a) {
      const tag = AMAZON_TAG ? `&tag=${enc(AMAZON_TAG)}` : "";
      targets.push(["Amazon", "書籍を探す", `https://www.amazon.co.jp/s?k=${enc(entry.a)}${tag}`, "lk-amazon"]);
    }
    if (entry.w) targets.push(["Wikipedia", "", `https://ja.wikipedia.org/w/index.php?search=${enc(entry.w)}`, ""]);
    if (entry.p) targets.push(["PubMed", "論文", `https://pubmed.ncbi.nlm.nih.gov/?term=${enc(entry.p)}`, ""]);
    return targets;
  };

  for (const element of document.querySelectorAll("[data-id]")) {
    const entry = LINKS[element.dataset.id];
    if (!entry || !linkTargets(entry).length) continue;
    element.classList.add("has-lk");
    if (!element.hasAttribute("title")) continue;
    element.dataset.tip = element.getAttribute("title");
    element.removeAttribute("title");
  }

  let menu = null;
  let menuItem = null;
  let openTimer = 0;
  let closeTimer = 0;

  const cancelOpen = () => { clearTimeout(openTimer); openTimer = 0; };
  const cancelClose = () => { clearTimeout(closeTimer); closeTimer = 0; };
  const closeMenu = () => {
    cancelOpen();
    cancelClose();
    if (!menu) return;
    menu.remove();
    menu = null;
    menuItem = null;
  };

  const buildMenu = (entry, tipText) => {
    const box = document.createElement("div");
    box.className = "lk-menu";
    const info = document.createElement("div");
    info.className = "lk-info";
    const head = document.createElement("div");
    head.className = "lk-h";
    head.textContent = entry.n;
    info.appendChild(head);
    if (tipText) {
      const tip = document.createElement("div");
      tip.className = "lk-tip";
      tip.textContent = tipText;
      info.appendChild(tip);
    }
    box.appendChild(info);
    for (const [label, note, href, className] of linkTargets(entry)) {
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.target = "_blank";
      // アフィリエイトを含むので sponsored を付ける
      anchor.rel = "noopener sponsored";
      if (className) anchor.className = className;
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

  // カーソルではなく項目の矩形に合わせる（カーソル基準だと動かすたびにメニューが跳ねる）。
  // getBoundingClientRect と position: fixed はどちらも iframe 内の座標なので、親ページの拡大縮小の影響を受けない
  const ownViewport = () => ({ left: 0, top: 0, right: innerWidth, bottom: innerHeight });
  const intersect = (first, second) => ({
    left: Math.max(first.left, second.left), top: Math.max(first.top, second.top),
    right: Math.min(first.right, second.right), bottom: Math.min(first.bottom, second.bottom),
  });

  // 公開サイトでは iframe を原寸大のまま親ページで拡大縮小・スクロールさせるので、iframe 自身の画面＝紙面全体になる。
  // 実際に見えている範囲（親の画面とスクロール枠に切り取られた部分）を iframe 内の座標で求め、そこに収める
  const visibleArea = () => {
    const viewport = ownViewport();
    let frame = null;
    try { frame = window.frameElement; } catch { return viewport; }
    if (!frame || !frame.offsetWidth) return viewport;
    const parentWindow = frame.ownerDocument.defaultView;
    let clip = { left: 0, top: 0, right: parentWindow.innerWidth, bottom: parentWindow.innerHeight };
    for (let ancestor = frame.parentElement; ancestor; ancestor = ancestor.parentElement) {
      if (parentWindow.getComputedStyle(ancestor).overflow === "visible") continue;
      // スクロールバーの下に潜らないよう、枠の内側（client 領域）で切る
      const rect = ancestor.getBoundingClientRect();
      const innerLeft = rect.left + ancestor.clientLeft;
      const innerTop = rect.top + ancestor.clientTop;
      clip = intersect(clip, {
        left: innerLeft, top: innerTop,
        right: innerLeft + ancestor.clientWidth, bottom: innerTop + ancestor.clientHeight,
      });
    }
    const frameRect = frame.getBoundingClientRect();
    const scale = frameRect.width / frame.offsetWidth;
    const visible = intersect(viewport, {
      left: (clip.left - frameRect.left) / scale, top: (clip.top - frameRect.top) / scale,
      right: (clip.right - frameRect.left) / scale, bottom: (clip.bottom - frameRect.top) / scale,
    });
    return visible.right > visible.left && visible.bottom > visible.top ? visible : viewport;
  };

  const placeMenu = (box, item) => {
    const area = visibleArea();
    const itemRect = item.getBoundingClientRect();
    const boxRect = box.getBoundingClientRect();
    const maxLeft = area.right - boxRect.width - MENU_MARGIN_PX;
    const left = Math.max(area.left + MENU_MARGIN_PX, Math.min(itemRect.left, maxLeft));
    let top = itemRect.bottom + ANCHOR_GAP_PX;
    if (top + boxRect.height > area.bottom - MENU_MARGIN_PX) top = itemRect.top - ANCHOR_GAP_PX - boxRect.height;
    box.style.left = `${left}px`;
    box.style.top = `${Math.max(area.top + MENU_MARGIN_PX, top)}px`;
  };

  const openMenuFor = (item) => {
    closeMenu();
    menu = buildMenu(LINKS[item.dataset.id], item.dataset.tip);
    menuItem = item;
    document.body.appendChild(menu);
    placeMenu(menu, item);
  };

  const scheduleClose = () => {
    cancelOpen();
    if (!menu || closeTimer) return;
    closeTimer = setTimeout(closeMenu, HOVER_CLOSE_GRACE_MS);
  };

  const isHoverPointer = (event) => event.pointerType !== "touch" && !NO_HOVER_QUERY.matches;

  document.addEventListener("pointerover", (event) => {
    if (!isHoverPointer(event)) return;
    if (menu && menu.contains(event.target)) {
      // 項目からメニューへ移る途中で隣の項目をかすめても、そちらに切り替えない
      cancelOpen();
      cancelClose();
      return;
    }
    const item = event.target.closest(".has-lk");
    if (!item) {
      scheduleClose();
      return;
    }
    cancelClose();
    if (item === menuItem) {
      cancelOpen();
      return;
    }
    cancelOpen();
    openTimer = setTimeout(() => openMenuFor(item), HOVER_OPEN_DELAY_MS);
  });
  // ページの外へ出たときは pointerover が来ないので、ここで閉じる準備をする
  document.addEventListener("pointerout", (event) => {
    if (isHoverPointer(event) && !event.relatedTarget) scheduleClose();
  });

  document.addEventListener("click", (event) => {
    if (menu && menu.contains(event.target)) return;
    const item = event.target.closest(".has-lk");
    if (!item) {
      closeMenu();
      return;
    }
    if (item !== menuItem) openMenuFor(item);
    cancelClose();
    event.stopPropagation();
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeMenu(); });
  addEventListener("scroll", closeMenu, true);
  // 公開サイトでは年表が iframe の中にあり、スクロールするのは親ページ（.viewer）の側なので、同じオリジンの親にも付ける
  for (let ancestor = window.parent; ancestor && ancestor !== window; ancestor = ancestor.parent) {
    try {
      ancestor.addEventListener("scroll", closeMenu, true);
    } catch {
      break;  // 別オリジン（ブログ記事の埋め込みなど）から先には届かない
    }
    if (ancestor === ancestor.parent) break;
  }
})();
