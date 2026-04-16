// =================================
// PocketBell Simulator Ver 1.0 by JA1XPM 2026/04/16
// =================================

window.my_call = "";
window.ur_call = "";

(() => {
  const lcd = document.getElementById("lcd");
  const glow = document.querySelector(".lcd-glow");
  const msgInput = document.getElementById("msg");
  const toggleBtn = document.getElementById("toggle");
  const inputError = document.getElementById("inputError");

  const setHotspot = document.getElementById("setHotspot");
  const upHotspot = document.getElementById("upHotspot");
  const downHotspot = document.getElementById("downHotspot");

  const myCallEditor = document.getElementById("myCallEditor");
  const myCallInput = document.getElementById("myCallInput");
  const myCallSave = document.getElementById("myCallSave");

  let backlight = false;
  const COLS = 24;
  const ROWS = 4;
  const PADDING = 6;
  const HEADER_PX_X = 40;
  const HEADER_PX_Y = 18;
  const LCD_PX_W = 822;
  const LCD_PX_H = 238;
  const MAX_HISTORY = 10;
  const MAX_BODY_CHARS = COLS;
  const NEW_MARK_X_PX = 2;
  const HEADER_DATE_X_PX = 68;
  const HEADER_TIME_EXTRA_SHIFT_PX = -20;
  const NEW_MARK_DURATION_MS = 5 * 60 * 1000;

  let historyLines = [];
  let scrollIndex = 0;
  let routeDisplay = "";
  let lastValidInput = "";
  let lastRxAt = 0;
  let ws = null;

  const CALL_MAP = {
    "A":"111","B":"112","C":"113","D":"114","E":"115",
    "F":"121","G":"122","H":"123","I":"124","J":"125",
    "K":"131","L":"132","M":"133","N":"134","O":"135",
    "P":"141","Q":"142","R":"143","S":"144","T":"145",
    "U":"151","V":"152","W":"153","X":"154","Y":"155","Z":"156"
  };

  const FREEWORD_MAP = {
    "ワ":"01","ヲ":"02","ン":"03",
    "ア":"11","イ":"12","ウ":"13","エ":"14","オ":"15","A":"16","B":"17","C":"18","D":"19","E":"10",
    "カ":"21","キ":"22","ク":"23","ケ":"24","コ":"25","F":"26","G":"27","H":"28","I":"29","J":"20",
    "サ":"31","シ":"32","ス":"33","セ":"34","ソ":"35","K":"36","L":"37","M":"38","N":"39","O":"30",
    "タ":"41","チ":"42","ツ":"43","テ":"44","ト":"45","P":"46","Q":"47","R":"48","S":"49","T":"40",
    "ナ":"51","ニ":"52","ヌ":"53","ネ":"54","ノ":"55","U":"56","V":"57","W":"58","X":"59","Y":"50",
    "ハ":"61","ヒ":"62","フ":"63","ヘ":"64","ホ":"65","Z":"66","?":"67","!":"68","ー":"69","/":"60",
    "マ":"71","ミ":"72","ム":"73","メ":"74","モ":"75","*":"76","&":"77","(":"78",")":"79","=":"70",
    "ヤ":"81","ユ":"82","ヨ":"83","ャ":"84","ュ":"85","ョ":"86","ッ":"87",
    "ラ":"91","リ":"92","ル":"93","レ":"94","ロ":"95",
    "0":"00","1":"96","2":"97","3":"98","4":"99","5":"90","6":"06","7":"07","8":"08","9":"09"
  };

  const FIXED_MESSAGE_MAP = {
    "01":"キンキュウ",
    "02":"TELセヨ",
    "03":"スグカエレ",
    "04":"シュウゴウ",
    "05":"デモチーフダサイ",
    "06":"スグニイケマス",
    "07":"チコクシマス",
    "08":"ペンシル",
    "09":"FAXスル",
    "10":"*4*410",
    "11":"サンキュウ",
    "12":"サキニイキマス",
    "13":"オクレマス",
    "14":"キャクアリ",
    "15":"トラブル",
    "16":"ヨヤクOK",
    "17":"スグニイキマス",
    "18":"OK",
    "19":"NO",
    "20":"ヨロシク",
    "21":"カイシャニTELシテクダサイ",
    "22":"ルスバンデンワシテクダサイ",
    "23":"ジッカニTELシテクダサイ",
    "24":"イマデンワシマシタ",
    "25":"キテクダサイ",
    "26":"ゴメンナサイ",
    "27":"アリガトウ",
    "28":"オツカレサマ",
    "29":"マッテマス",
    "30":"*4*430"
  };

  function saveState(){
    try{
      localStorage.setItem("my_call", window.my_call || "");
      localStorage.setItem("historyLines", JSON.stringify(historyLines));
      localStorage.setItem("scrollIndex", String(scrollIndex));
      localStorage.setItem("routeDisplay", routeDisplay || "");
      localStorage.setItem("lastRxAt", String(lastRxAt || 0));
    }catch{}
  }

  function loadState(){
    try{
      const savedCall = localStorage.getItem("my_call");
      if(savedCall !== null) window.my_call = savedCall;
      const savedHist = localStorage.getItem("historyLines");
      if(savedHist){
        const parsed = JSON.parse(savedHist);
        if(Array.isArray(parsed)) historyLines = parsed.slice(-MAX_HISTORY);
      }
      scrollIndex = Math.max(0, historyLines.length - 2);
      const savedRoute = localStorage.getItem("routeDisplay");
      if(savedRoute) routeDisplay = savedRoute;
      lastRxAt = Number(localStorage.getItem("lastRxAt") || "0") || 0;
    }catch{}
  }

  function updateMyCallRemote(){
    if(!ws || ws.readyState !== 1) return;
    ws.send(JSON.stringify({ type:"set_my_call", my_call: window.my_call || "" }));
  }

  function wsConnect(){
    try{
      ws = new WebSocket("ws://127.0.0.1:8765");
      ws.onopen = () => {
        updateMyCallRemote();
      };
      ws.onclose = () => {};
      ws.onerror = () => {};
      ws.onmessage = (ev) => {
        try{
          const data = JSON.parse(ev.data);
          if(data.type === "rx_message"){
            routeDisplay = `${data.from || ""} > ${window.my_call || data.to || ""}`;
            window.ur_call = data.from || "";
            lastRxAt = Date.now();
            addHistoryLine(`→${data.from || ""} ${data.body || ""}`);
          }
        }catch{}
      };
    }catch{}
  }

  function showError(message){
    inputError.textContent = message;
    clearTimeout(showError._timer);
    showError._timer = setTimeout(() => {
      inputError.textContent = "";
    }, 1000);
  }

  function addHistoryLine(line){
    const text = String(line || "").slice(0, COLS);
    historyLines.push(text);
    if(historyLines.length > MAX_HISTORY){
      historyLines.shift();
    }
    scrollIndex = Math.max(0, historyLines.length - 2);
    saveState();
    render();
  }

  function scrollUp(){
    if(scrollIndex > 0){
      scrollIndex -= 1;
      saveState();
      render();
    }
  }

  function scrollDown(){
    const maxIndex = Math.max(0, historyLines.length - 2);
    if(scrollIndex < maxIndex){
      scrollIndex += 1;
      saveState();
      render();
    }
  }

  function visibleLines(){
    return [
      historyLines[scrollIndex] || "",
      historyLines[scrollIndex + 1] || ""
    ];
  }

  function splitAddressAndBody(s){
    const text = String(s || "");
    const idxAscii = text.indexOf(",");
    const idxJp = text.indexOf("，");
    let idx = -1;
    if(idxAscii >= 0 && idxJp >= 0) idx = Math.min(idxAscii, idxJp);
    else idx = Math.max(idxAscii, idxJp);
    if(idx < 0) return { dest:"CQ", body:text.trim() };
    const dest = text.slice(0, idx).trim() || "CQ";
    const body = text.slice(idx + 1).trim();
    return { dest, body };
  }

  function encodeCallsign(s){
    let out = "";
    const text = String(s || "").toUpperCase();
    for(const ch of text){
      if(ch >= "0" && ch <= "9"){
        out += ch;
      }else if(CALL_MAP[ch]){
        out += CALL_MAP[ch];
      }
    }
    return out;
  }

  function normalizeFreewordText(s){
    return String(s || "")
      .normalize("NFKC")
      .toUpperCase()
      .replace(/[\u3041-\u3096]/g, ch =>
        String.fromCharCode(ch.charCodeAt(0) + 0x60)
      );
  }

  function encodeFreewordBody(s){
    let out = "";
    const text = normalizeFreewordText(s).normalize("NFD");
    for(const ch of text){
      if(FREEWORD_MAP[ch]){
        out += FREEWORD_MAP[ch];
      }else if(ch === "\u3099"){
        out += "04";
      }else if(ch === "\u309A"){
        out += "05";
      }else{
        throw new Error(`unsupported:${ch}`);
      }
    }
    return out;
  }

  function parseMessageCommand(bodyText){
    const body = String(bodyText || "").trim();
    if(body.startsWith("*2*2")){
      const displayText = normalizeFreewordText(body.slice(4).trim());
      if(!displayText) throw new Error("empty_freeword");
      return {
        mode: "freeword",
        displayText,
        encodedBody: "*2*2" + encodeFreewordBody(displayText)
      };
    }
    if(body.startsWith("*4*4")){
      const code = body.slice(4).trim();
      if(!/^\d{2}$/.test(code)){
        throw new Error("invalid_fixed");
      }
      return {
        mode: "fixed",
        displayText: FIXED_MESSAGE_MAP[code] || `*4*4${code}`,
        encodedBody: `*4*4${code}`
      };
    }
    throw new Error("missing_command");
  }

  function displayLengthForInput(bodyText){
    const body = String(bodyText || "").trim();
    if(!body) return 0;
    try{
      return parseMessageCommand(body).displayText.length;
    }catch{
      if(body.startsWith("*2*2")){
        return normalizeFreewordText(body.slice(4).trim()).length;
      }
      return body.length;
    }
  }

  function buildDtmfMessage(rawInput){
    const parts = splitAddressAndBody(rawInput);
    const dest = encodeCallsign(parts.dest || "CQ");
    const from = encodeCallsign(window.my_call || "");
    const command = parseMessageCommand(parts.body);
    return {
      dest: (parts.dest || "CQ").toUpperCase(),
      displayText: command.displayText,
      seq: "*2*2" + dest + "A0A" + from + "A0A" + command.encodedBody + "##"
    };
  }

  function sendTx(seq){
    if(!ws || ws.readyState !== 1) return false;
    ws.send(JSON.stringify({ type:"tx", seq }));
    return true;
  }

  function showMyCallEditor(){
    if(!myCallEditor) return;
    myCallInput.value = window.my_call || "";
    myCallEditor.classList.remove("hidden");
    myCallInput.focus();
  }

  function hideMyCallEditor(){
    if(!myCallEditor) return;
    myCallEditor.classList.add("hidden");
  }

  function headerRightText(){
    return routeDisplay || window.my_call || "";
  }

  function formatHeaderParts(d){
    const m = d.getMonth() + 1;
    const day = d.getDate();
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return {
      date: `${m}月${day}日`,
      time: `${hh}:${mm}`
    };
  }

  function render(){
    const dpr = window.devicePixelRatio || 1;
    const rect = lcd.getBoundingClientRect();
    lcd.width = Math.round(rect.width * dpr);
    lcd.height = Math.round(rect.height * dpr);

    const ctx = lcd.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;

    const off = document.createElement("canvas");
    const cellW = 6;
    const cellH = 10;
    off.width = COLS * cellW + PADDING * 2;
    off.height = ROWS * cellH + PADDING * 2;
    const octx = off.getContext("2d");
    octx.imageSmoothingEnabled = false;
    octx.clearRect(0, 0, off.width, off.height);

    const sx = off.width / LCD_PX_W;
    const sy = off.height / LCD_PX_H;

    const ink = getComputedStyle(document.documentElement).getPropertyValue("--lcd-ink").trim() || "#1b261b";
    octx.fillStyle = ink;
    octx.font = "10px 'MS Gothic','ＭＳ ゴシック',monospace";
    octx.textBaseline = "top";

    const header = formatHeaderParts(new Date());
    const showNewMark = (Date.now() - lastRxAt) < NEW_MARK_DURATION_MS;
    if(showNewMark){
      octx.save();
      octx.font = "9px 'MS Gothic','ＭＳ ゴシック',monospace";
      octx.fillText("※", NEW_MARK_X_PX * sx, HEADER_PX_Y * sy);
      octx.restore();
    }
    octx.save();
    octx.shadowColor = "rgba(0,0,0,0.30)";
    octx.shadowOffsetX = 1;
    octx.shadowOffsetY = 1;
    const headerDateX = HEADER_DATE_X_PX * sx;
    octx.fillText(header.date, headerDateX, HEADER_PX_Y * sy);
    const headerTimeX = headerDateX + octx.measureText(`${header.date} `).width + (HEADER_TIME_EXTRA_SHIFT_PX * sx);
    octx.fillText(header.time, headerTimeX, HEADER_PX_Y * sy);
    octx.restore();

    const rightText = headerRightText();
    if(rightText){
      octx.save();
      octx.textAlign = "right";
      octx.shadowColor = "rgba(0,0,0,0.30)";
      octx.shadowOffsetX = 1;
      octx.shadowOffsetY = 1;
      octx.fillText(rightText, (LCD_PX_W - 10) * sx, HEADER_PX_Y * sy);
      octx.restore();
      octx.textAlign = "left";
    }

    const lines = visibleLines();
    octx.save();
    octx.translate(PADDING, PADDING + 13);
    octx.scale(0.78, 1.35);
    octx.font = "8px 'MS Gothic','ＭＳ ゴシック',monospace";
    octx.fillText(lines[0] || "", 0, 0);
    octx.fillText(lines[1] || "", 0, 11);
    octx.restore();

    octx.fillStyle = "rgba(0,0,0,0.06)";
    for(let y = PADDING; y < off.height - PADDING; y += 2){
      octx.fillRect(0, y, off.width, 1);
    }

    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.drawImage(off, 0, 0, off.width, off.height, 0, 0, rect.width, rect.height);

    glow.style.opacity = backlight ? "1" : "0";
  }

  loadState();
  wsConnect();

  if(setHotspot){
    setHotspot.addEventListener("click", showMyCallEditor);
  }
  if(upHotspot){
    upHotspot.addEventListener("click", scrollUp);
  }
  if(downHotspot){
    downHotspot.addEventListener("click", scrollDown);
  }
  if(myCallSave){
    myCallSave.addEventListener("click", () => {
      window.my_call = (myCallInput.value || "").trim().toUpperCase();
      saveState();
      updateMyCallRemote();
      hideMyCallEditor();
      render();
    });
  }

  toggleBtn.addEventListener("click", () => {
    backlight = !backlight;
    toggleBtn.textContent = backlight ? "バックライトOFF" : "バックライト";
    render();
  });

  msgInput.addEventListener("input", () => {
    const body = splitAddressAndBody(msgInput.value || "").body;
    if(displayLengthForInput(body) > MAX_BODY_CHARS){
      msgInput.value = lastValidInput;
      showError("入力文字数オーバー");
      return;
    }
    lastValidInput = msgInput.value;
  });

  msgInput.addEventListener("keydown", (e) => {
    if(e.key === "Enter"){
      const parsed = splitAddressAndBody(msgInput.value || "");
      if(displayLengthForInput(parsed.body) > MAX_BODY_CHARS){
        showError("入力文字数オーバー");
        e.preventDefault();
        return;
      }
      try{
        const built = buildDtmfMessage(msgInput.value || "");
        const sent = sendTx(built.seq);
        if(sent){
          routeDisplay = `${built.dest} < ${window.my_call || ""}`;
          addHistoryLine(`←${built.dest} ${built.displayText}`);
        }
      }catch(err){
        if(err && err.message === "missing_command"){
          showError("本文は*2*2または*4*4で開始");
        }else if(err && err.message === "invalid_fixed"){
          showError("定型文は*4*4+2桁番号");
        }else if(err && err.message === "empty_freeword"){
          showError("本文が空です");
        }else{
          showError("本文に未対応文字があります");
        }
      }
      e.preventDefault();
    }
  });

  window.addEventListener("resize", render);
  setInterval(render, 1000);
  render();
})();
