/*
 * Purpose: 版面が紙（297mm から上下余白とフッタを除いた高さ）に収まるまで、本文の大きさ --fs を縮め、
 *          それでも溢れたら drop_levels の重要度の項目を非表示にする（ブラウザの組版結果を実測して決める）
 * Inputs:  render.py が出す .canvas（.spread / .side-left / .foot-left）。.it[data-drop] が落としてよい項目。
 *          .spread の data-sync-mode / data-sync-tol / data-font-step / data-drop-levels（profile の値）
 * Outputs: 各 .canvas の --fs と .is-hidden、.fit-info の表示、<html data-fit-*>（build.py が --dump-dom で読む）
 * Depends: なし（render.py が <script> に埋め込む）
 */
(() => {
  const FONT_START_PT = 9; // 列をそろえない版は余白が大きいので 6.5pt で頭打ちにしない
  const FONT_MIN_PT = 4.8;
  const DEFAULT_FONT_STEP_PT = 0.1;
  const FONT_DIGITS = 2;
  const MARGIN_ABOVE_FOOTER_PX = 4; // 版面の最下段とフッタの罫線がくっつかないように
  const PX_PER_MM = 96 / 25.4;
  const PX_PER_PT = 96 / 72;
  const BAND_STEP_PX = 0.5 * PX_PER_PT;

  const spreadOverflowPx = (canvas) => {
    const spreadBottom = canvas.querySelector(".spread").getBoundingClientRect().bottom;
    const footerTop = canvas.querySelector(".foot-left").getBoundingClientRect().top;
    return spreadBottom - (footerTop - MARGIN_ABOVE_FOOTER_PX);
  };
  const sideOverflowPx = (canvas) => {
    const side = canvas.querySelector(".side-left");
    return side.scrollHeight - side.clientHeight;
  };
  const isFitting = (canvas) => spreadOverflowPx(canvas) <= 0 && sideOverflowPx(canvas) <= 0;

  // 縦帯がセルの末尾で下へはみ出すと、その 1 本のために区間の行全体が伸びる。
  // 帯の下端が本文の下端を越えるあいだ、帯を 1 つ前の年ブロックへ繰り上げる。
  // 先頭まで上げても長いときは、折らずに帯の字を下限（--vband-min）まで縮める
  const previousVisibleBlock = (block) => {
    let previous = block.previousElementSibling;
    while (previous && (!previous.classList.contains("yb") || previous.classList.contains("is-hidden"))) {
      previous = previous.previousElementSibling;
    }
    return previous;
  };
  const contentBottom = (flow) => Math.max(...[...flow.querySelectorAll(".yb:not(.is-hidden)")]
    .map((yb) => yb.getBoundingClientRect().bottom));
  const isBandTooLong = (band, flow) => band.getBoundingClientRect().bottom > contentBottom(flow) + 1;

  const placeBands = (canvas) => {
    for (const band of canvas.querySelectorAll(".vband")) {
      band.homeBlock ??= band.parentElement;
      band.style.fontSize = "";
      band.homeBlock.prepend(band);
    }
    for (const flow of canvas.querySelectorAll(".flow")) {
      for (const band of [...flow.querySelectorAll(".vband")].reverse()) {
        let block = band.parentElement;
        while (isBandTooLong(band, flow) && previousVisibleBlock(block)) {
          block = previousVisibleBlock(block);
          block.prepend(band);
        }
        const minPx = parseFloat(getComputedStyle(canvas).getPropertyValue("--vband-min")) * PX_PER_PT;
        let sizePx = parseFloat(getComputedStyle(band).fontSize);
        while (isBandTooLong(band, flow) && sizePx - BAND_STEP_PX >= minPx) {
          sizePx -= BAND_STEP_PX;
          band.style.fontSize = `${sizePx}px`;
        }
      }
    }
  };

  const itemCount = (cell) => cell.querySelectorAll(".it").length;

  const moveRuleDown = (rule, currentTop, targetTop) => {
    const basePx = parseFloat(getComputedStyle(rule).marginTop);
    rule.style.marginTop = `${basePx + targetTop - currentTop}px`;
  };

  // ソフト同期: 同じ年の目印（.sync-rule）の高さの差を、許容幅（mm）を超える分だけ下へ詰める。
  // lowest は最も下の目印に寄せる。anchor は項目が最も多い列を動かさず他の列を寄せる
  // （最長の列を詰めたまま他の列をそろえるので、字を大きく保てる。基準より下の列はそのまま）。
  // 空欄列（.cell-blank）の目印は高さを決めさせず、項目のある列に合わせる（最下段より上なので版面は伸びない）
  const alignSyncRules = (canvas) => {
    const rules = [...canvas.querySelectorAll(".sync-rule")];
    rules.forEach((rule) => { rule.style.marginTop = ""; });
    const spread = canvas.querySelector(".spread");
    const tolerancePx = parseFloat(spread.dataset.syncTol || "0") * PX_PER_MM;
    const isAnchorMode = spread.dataset.syncMode === "anchor";
    const years = [...new Set(rules.map((rule) => rule.dataset.sync))].sort((a, b) => a - b);
    for (const year of years) {
      const group = rules.filter((rule) => rule.dataset.sync === year);
      const filled = group.filter((rule) => !rule.closest(".cell-blank"));
      const blank = group.filter((rule) => rule.closest(".cell-blank"));
      if (filled.length === 0) continue;
      const tops = filled.map((rule) => rule.getBoundingClientRect().top);
      const anchor = filled.reduce((best, rule) =>
        (itemCount(rule.closest(".cell")) > itemCount(best.closest(".cell")) ? rule : best));
      const referenceTop = isAnchorMode ? anchor.getBoundingClientRect().top : Math.max(...tops);
      const target = referenceTop - tolerancePx;
      filled.forEach((rule, index) => {
        if (tops[index] < target) moveRuleDown(rule, tops[index], target);
      });
      const alignedTops = filled.map((rule) => rule.getBoundingClientRect().top).sort((a, b) => a - b);
      const blankTop = isAnchorMode ? referenceTop : alignedTops[Math.floor((alignedTops.length - 1) / 2)];
      blank.forEach((rule) => {
        const top = rule.getBoundingClientRect().top;
        if (top < blankTop) moveRuleDown(rule, top, blankTop);
      });
    }
  };

  const setFont = (canvas, pt) => {
    canvas.style.setProperty("--fs", `${pt.toFixed(FONT_DIGITS)}pt`);
    placeBands(canvas);
    alignSyncRules(canvas);
  };

  // 刻みを足し引きで重ねると 0.02 の誤差が積もるので、段数から毎回計算する
  const shrinkFont = (canvas) => {
    const step = parseFloat(canvas.querySelector(".spread").dataset.fontStep) || DEFAULT_FONT_STEP_PT;
    let stepCount = 0;
    const ptAt = (count) => FONT_START_PT - count * step;
    setFont(canvas, ptAt(stepCount));
    while (!isFitting(canvas) && ptAt(stepCount + 1) >= FONT_MIN_PT - 1e-9) {
      stepCount += 1;
      setFont(canvas, ptAt(stepCount));
    }
    return ptAt(stepCount);
  };

  // 行の高さは「その時代でいちばん長い列」で決まるので、背の高い行の最長セルから落とす
  const tallestCellsByRow = (canvas) => {
    const rows = new Map();
    for (const cell of canvas.querySelectorAll(".cell:not(.cell-blank)")) {
      const height = cell.querySelector(".flow").offsetHeight;
      const current = rows.get(cell.dataset.era);
      if (!current || height > current.height) rows.set(cell.dataset.era, { cell, height });
    }
    return [...rows.values()].sort((a, b) => b.height - a.height);
  };

  const hideItem = (item) => {
    item.classList.add("is-hidden");
    const block = item.closest(".yb");
    const hasVisible = [...block.querySelectorAll(".it, .vband")].some((el) => !el.classList.contains("is-hidden"));
    if (!hasVisible) block.classList.add("is-hidden");
    hideEmptyEraHeads(block.closest(".flow"));
  };

  // 時代見出しの後ろの項目がすべて非表示になったら、見出しも消す
  const hideEmptyEraHeads = (flow) => {
    for (const head of flow.querySelectorAll(".era-sub")) {
      let next = head.nextElementSibling;
      let hasVisible = false;
      while (next && !next.classList.contains("era-sub")) {
        if (!next.classList.contains("is-hidden")) hasVisible = true;
        next = next.nextElementSibling;
      }
      head.classList.toggle("is-hidden", !hasVisible);
    }
  };

  const dropItems = (canvas) => {
    const hiddenIds = [];
    const dropLevels = (canvas.querySelector(".spread").dataset.dropLevels || "").split(" ").filter(Boolean);
    for (const level of dropLevels) {
      while (spreadOverflowPx(canvas) > 0) {
        const target = tallestCellsByRow(canvas)
          .map(({ cell }) => [...cell.querySelectorAll(`.it[data-drop="${level}"]:not(.is-hidden)`)].pop())
          .find(Boolean);
        if (!target) break;
        hideItem(target);
        placeBands(canvas);
        alignSyncRules(canvas);
        hiddenIds.push(target.dataset.id);
      }
    }
    return hiddenIds;
  };

  const results = [...document.querySelectorAll(".canvas")].map((canvas) => {
    const fontPt = shrinkFont(canvas);
    const hiddenIds = dropItems(canvas);
    const spreadOver = spreadOverflowPx(canvas);
    const sideOver = sideOverflowPx(canvas);
    const info = canvas.querySelector(".fit-info");
    const warning = spreadOver > 0 || sideOver > 0 ? "・溢れあり" : "";
    if (info) info.textContent = `本文 ${fontPt.toFixed(FONT_DIGITS)}pt・紙幅で非表示 ${hiddenIds.length} 件${warning}`;
    return { fontPt, hiddenIds, spreadOverMm: spreadOver / PX_PER_MM, sideOverMm: sideOver / PX_PER_MM };
  });

  const first = results[0];
  if (!first) return;
  const root = document.documentElement;
  root.dataset.fitFont = first.fontPt.toFixed(FONT_DIGITS);
  root.dataset.fitHidden = String(first.hiddenIds.length);
  root.dataset.fitHiddenIds = first.hiddenIds.join(" ");
  root.dataset.fitSpreadOverMm = first.spreadOverMm.toFixed(1);
  root.dataset.fitSideOverMm = first.sideOverMm.toFixed(1);
})();
