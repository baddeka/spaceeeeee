"use strict";

// Pixel-art office drawn on a 320x180 canvas and scaled up without smoothing.
// Every object is plain rectangles or a sprite string, so the whole scene lives in this file.
(() => {
  const W = 320;
  const H = 180;
  const FPS = 8;

  const C = {
    outline: "#2b2433",
    wallTop: "#c7d1e0",
    wallShade: "#b3bfd2",
    wains1: "#6c7da3",
    wains2: "#7b8cb2",
    trim: "#56658a",
    base: "#8a5a3c",
    baseDark: "#6e4530",
    floor: "#eaa96b",
    floorDark: "#d18a4e",
    floorLight: "#f5c18c",
    wood: "#f1dcae",
    woodLight: "#fbecc8",
    woodSide: "#d4b27e",
    woodDark: "#a9844f",
    shelfBack: "#6d4a2e",
    door: "#b8703c",
    doorDark: "#8e522a",
    doorPanel: "#cc8550",
    metal: "#3d4255",
    metalLight: "#5a6078",
    screen: "#16232f",
    plastic: "#d9dbe3",
    plasticDark: "#9a9cab",
    chair: "#5c6680",
    chairLight: "#76819c",
    chairDark: "#454d63",
    skin: "#f0c095",
    white: "#f4f1ea",
    paper: "#fbfaf5",
    leaf: "#3f9a4a",
    leafLight: "#66c06a",
    leafDark: "#2c7339",
    pot: "#a4532f",
    potDark: "#7f3d22",
    red: "#e04848",
    green: "#45b552",
    blue: "#3b7bd9",
    purple: "#8b55d6",
    yellow: "#f2cd4b",
    water: "#9fd3f5",
  };

  const AGENTS = {
    worker: { cx: 90, shirt: "#3b7bd9", shirtDark: "#2c5fae", hair: "#2d2a26", hairLight: "#4a443d" },
    reviewer: { cx: 228, shirt: "#8b55d6", shirtDark: "#6a3fae", hair: "#8a4a26", hairLight: "#a8633a" },
  };
  const DESK_Y = 96;

  const SPRITES = {
    headWorker: [
      "..HHHHHH..",
      ".HKKKKKKH.",
      "HKHhhHHHKH",
      "KHHHHHHHHK",
      "KHHHHHHHHK",
      "KHHHHHHHHK",
      ".HHHHHHHH.",
      "..SSSSSS..",
      "...SSSS...",
    ],
    headReviewer: [
      "...HHHH...",
      "...HhHH...",
      "..HHHHHH..",
      ".HHhhHHHH.",
      "HHHHHHHHHH",
      "SHHHHHHHHS",
      "SHHHHHHHHS",
      ".HHHHHHHH.",
      "..SSSSSS..",
      "...SSSS...",
    ],
    body: [
      "...TTTTTTTT...",
      ".TTTTTTTTTTTT.",
      "TTTTTTTTTTTTTT",
      "TTTTTTTTTTTTTT",
      "tTTTTTTTTTTTTt",
      "tTTTTTTTTTTTTt",
      "tTTTTTTTTTTTTt",
    ],
    chair: [
      "..OOOOOOOOOOOO..",
      ".OLLLLLLLLLLLLO.",
      "OLLCCCCCCCCCCLLO",
      "OLCCCCCCCCCCCCDO",
      "OLCCCCCCCCCCCCDO",
      "OLCCCCCCCCCCCCDO",
      "OLCCCCCCCCCCCCDO",
      "OLCCCCCCCCCCCCDO",
      "OLCCCCCCCCCCCCDO",
      "OLCCCCCCCCCCCCDO",
      "OLCCCCCCCCCCCDDO",
      ".ODDDDDDDDDDDDO.",
      "..OOOOOOOOOOOO..",
    ],
    clock: [
      "..OOOOO..",
      ".OWWWWWO.",
      "OWWWWWWWO",
      "OWWWWWWWO",
      "OWWWWWWWO",
      "OWWWWWWWO",
      "OWWWWWWWO",
      ".OWWWWWO.",
      "..OOOOO..",
    ],
    check: [
      "........W",
      ".......WW",
      "W.....WW.",
      "WW...WW..",
      ".WW.WW...",
      "..WWW....",
      "...W.....",
    ],
    cross: [
      "WW...WW",
      ".WW.WW.",
      "..WWW..",
      ".WW.WW.",
      "WW...WW",
    ],
    lens: [
      ".WWW...",
      "W...W..",
      "W...W..",
      "W...W..",
      ".WWW...",
      "....BB.",
      ".....BB",
    ],
    paper: [
      "OOOOOOOO..",
      "OPPPPPPOO.",
      "OPddddPPOO",
      "OPPPPPPPPO",
      "OPdddddPPO",
      "OPPPPPPPPO",
      "OPddddPPPO",
      "OPPPPPPPPO",
      "OPdddPPPPO",
      "OPPPPPPPPO",
      "OOOOOOOOOO",
    ],
    plant: [
      ".....G.....g....",
      "....GG....gg..G.",
      "..g.GLG..gLg.GG.",
      ".gg.GLGG.gLgGLG.",
      ".gLg.GLG.gLgGLG.",
      "..gLg.GLggLGLG..",
      "...gLgGLgLGLG.g.",
      ".G..gLGLLLGLGgg.",
      ".GG..gLLLLLGgLg.",
      "..GLG.gLLLLgLg..",
      "...GLGgLLLLLg...",
      "....GLLLLLLL....",
      ".....GLLLLL.....",
      "......LLLL......",
      "...OOOOOOOOOO...",
      "...OPPPPPPPPO...",
      "....OPPPPPPO....",
      "....OPPPPPPO....",
      "....OpPPPPpO....",
      ".....OpppPO.....",
      ".....OOOOOO.....",
    ],
  };

  // ---------- drawing helpers ----------

  function rect(c, x, y, w, h, color) {
    c.fillStyle = color;
    c.fillRect(Math.round(x), Math.round(y), w, h);
  }

  function sprite(c, rows, x, y, pal) {
    for (let j = 0; j < rows.length; j++) {
      const row = rows[j];
      for (let i = 0; i < row.length; i++) {
        const color = pal[row[i]];
        if (color) rect(c, x + i, y + j, 1, 1, color);
      }
    }
  }

  function seeded(seed) {
    let s = seed;
    return () => {
      s = (s * 1103515245 + 12345) & 0x7fffffff;
      return s / 0x7fffffff;
    };
  }

  // ---------- static background ----------

  function drawWall(c) {
    rect(c, 0, 0, W, 36, C.wallTop);
    rect(c, 0, 0, W, 2, C.wallShade);
    for (let y = 37; y < 60; y += 2) {
      for (let x = 0; x < W; x += 2) {
        rect(c, x, y, 2, 2, ((x + y) / 2) % 2 ? C.wains1 : C.wains2);
      }
    }
    rect(c, 0, 35, W, 2, C.trim);
    rect(c, 0, 60, W, 4, C.base);
    rect(c, 0, 64, W, 1, C.baseDark);
  }

  function drawFloor(c) {
    for (let row = 0, y = 65; y < H; row++, y += 8) {
      const offset = row % 2 ? -8 : 0;
      for (let x = offset; x < W; x += 16) {
        rect(c, x, y, 16, 8, C.floor);
        rect(c, x, y, 15, 1, C.floorLight);
        rect(c, x, y + 7, 16, 1, C.floorDark);
        rect(c, x + 15, y, 1, 8, C.floorDark);
        rect(c, x + 4, y + 3, 1, 1, C.floorDark);
        rect(c, x + 10, y + 4, 1, 1, C.floorDark);
      }
    }
    // shadow where the floor meets the wall
    c.fillStyle = "rgba(90, 50, 20, 0.18)";
    c.fillRect(0, 65, W, 3);
  }

  function drawDoor(c, x) {
    rect(c, x - 2, 10, 34, 54, C.outline);
    rect(c, x - 1, 11, 32, 53, C.doorDark);
    rect(c, x + 1, 13, 28, 51, C.door);
    rect(c, x + 5, 18, 20, 13, C.outline);
    rect(c, x + 6, 19, 18, 11, C.doorPanel);
    rect(c, x + 6, 19, 18, 1, "#dc9a66");
    rect(c, x + 24, 40, 3, 3, C.outline);
    rect(c, x + 24, 40, 2, 2, C.yellow);
  }

  function drawBookshelf(c, x, seed) {
    const y = 12;
    const w = 26;
    const h = 62;
    const rnd = seeded(seed);
    const books = ["#c0392b", "#2e7d5b", "#2f5fae", "#7a3fa0", "#d98c2b", "#3b3b4f", "#b5485c"];
    rect(c, x, y, w, h, C.outline);
    rect(c, x + 1, y + 1, w - 2, h - 2, C.woodSide);
    rect(c, x + 1, y + 1, w - 2, 3, C.wood);
    rect(c, x + 3, y + 6, w - 6, 30, C.shelfBack);
    for (const shelfY of [y + 20, y + 36]) {
      let bx = x + 3;
      while (bx < x + w - 4) {
        const bw = rnd() < 0.5 ? 2 : 3;
        const bh = 9 + Math.floor(rnd() * 4);
        rect(c, bx, shelfY - bh, bw, bh, books[Math.floor(rnd() * books.length)]);
        rect(c, bx, shelfY - bh, 1, bh, "rgba(255,255,255,0.18)");
        bx += bw + (rnd() < 0.2 ? 1 : 0);
      }
      rect(c, x + 2, shelfY, w - 4, 2, C.wood);
    }
    rect(c, x + 3, y + 40, 9, 19, C.wood);
    rect(c, x + 14, y + 40, 9, 19, C.wood);
    rect(c, x + 3, y + 40, 9, 1, C.woodLight);
    rect(c, x + 14, y + 40, 9, 1, C.woodLight);
    rect(c, x + 10, y + 48, 1, 3, C.woodDark);
    rect(c, x + 15, y + 48, 1, 3, C.woodDark);
    rect(c, x, y + h, w, 2, "rgba(90, 50, 20, 0.25)");
  }

  function drawPicture(c, x, y) {
    rect(c, x, y, 24, 20, C.outline);
    rect(c, x + 1, y + 1, 22, 18, C.doorDark);
    rect(c, x + 3, y + 3, 18, 14, "#7fc3f0");
    rect(c, x + 3, y + 12, 18, 5, "#5bb560");
    rect(c, x + 6, y + 9, 2, 5, "#7a4a26");
    rect(c, x + 4, y + 5, 6, 5, "#3f9a4a");
    rect(c, x + 5, y + 4, 4, 1, "#3f9a4a");
    rect(c, x + 16, y + 5, 3, 2, C.white);
    rect(c, x + 15, y + 6, 5, 1, C.white);
  }

  function drawNote(c, x, y) {
    rect(c, x, y, 11, 14, C.outline);
    rect(c, x + 1, y + 1, 9, 12, C.paper);
    for (let i = 0; i < 4; i++) rect(c, x + 2, y + 3 + i * 2, 4 + (i % 2) * 3, 1, C.plasticDark);
    rect(c, x + 5, y, 1, 1, C.red);
  }

  function drawBoard(c, x, y) {
    rect(c, x, y, 50, 32, C.outline);
    rect(c, x + 1, y + 1, 48, 30, C.metalLight);
    rect(c, x + 2, y + 2, 46, 26, "#f7f9fb");
    rect(c, x + 17, y + 3, 1, 24, "#d5dae3");
    rect(c, x + 32, y + 3, 1, 24, "#d5dae3");
    rect(c, x + 4, y + 4, 11, 2, C.blue);
    rect(c, x + 19, y + 4, 11, 2, C.purple);
    rect(c, x + 34, y + 4, 12, 2, C.green);
    rect(c, x + 8, y + 29, 34, 2, C.metal);
    rect(c, x + 12, y + 28, 5, 1, C.red);
    rect(c, x + 20, y + 28, 5, 1, C.blue);
  }

  function drawCooler(c, x, y) {
    rect(c, x + 3, y, 12, 16, C.outline);
    rect(c, x + 4, y + 1, 10, 14, C.water);
    rect(c, x + 5, y + 2, 2, 11, "#d4edfb");
    rect(c, x + 6, y - 2, 6, 3, C.outline);
    rect(c, x + 7, y - 1, 4, 2, "#5fa8d8");
    rect(c, x, y + 15, 18, 34, C.outline);
    rect(c, x + 1, y + 16, 16, 32, "#b9c2d1");
    rect(c, x + 1, y + 16, 16, 2, "#d2d9e4");
    rect(c, x + 3, y + 22, 12, 8, "#8d97ab");
    rect(c, x + 5, y + 24, 2, 3, C.red);
    rect(c, x + 11, y + 24, 2, 3, C.blue);
    rect(c, x + 4, y + 31, 10, 2, C.metal);
    rect(c, x, y + 49, 18, 2, "rgba(90, 50, 20, 0.25)");
  }

  function drawRug(c, x, y) {
    rect(c, x, y, 44, 30, "#9b3a4d");
    rect(c, x + 2, y + 2, 40, 26, "#b5485c");
    rect(c, x + 5, y + 5, 34, 20, "#c9606f");
    for (let i = 0; i < 4; i++) rect(c, x + 9 + i * 8, y + 13, 4, 4, "#e08a8f");
    for (let i = 0; i < 11; i++) {
      rect(c, x + 1 + i * 4, y - 2, 1, 2, "#e8d3a8");
      rect(c, x + 1 + i * 4, y + 30, 1, 2, "#e8d3a8");
    }
  }

  function drawBin(c, x, y) {
    rect(c, x, y, 9, 10, C.outline);
    rect(c, x + 1, y + 1, 7, 9, "#8d97ab");
    rect(c, x + 1, y + 1, 7, 1, "#aab3c4");
    rect(c, x + 3, y + 3, 1, 6, "#76809a");
    rect(c, x + 6, y + 3, 1, 6, "#76809a");
    rect(c, x + 2, y - 2, 4, 3, C.paper);
    rect(c, x + 3, y - 3, 2, 1, C.paper);
  }

  function drawCoffee(c, x, y) {
    rect(c, x, y, 30, 6, C.outline);
    rect(c, x + 1, y + 1, 28, 4, C.wood);
    rect(c, x + 1, y + 5, 28, 6, C.woodSide);
    rect(c, x + 2, y + 11, 2, 8, C.woodDark);
    rect(c, x + 26, y + 11, 2, 8, C.woodDark);
    rect(c, x + 4, y - 13, 12, 14, C.outline);
    rect(c, x + 5, y - 12, 10, 12, "#4a4f63");
    rect(c, x + 6, y - 11, 8, 3, "#6f768f");
    rect(c, x + 8, y - 6, 4, 4, "#22252f");
    rect(c, x + 12, y - 10, 1, 1, C.red);
    rect(c, x + 20, y - 3, 4, 4, C.white);
    rect(c, x + 24, y - 2, 1, 2, C.white);
  }

  function drawDesk(c, cx, side) {
    const x = cx - 30;
    const y = DESK_Y;
    rect(c, x - 1, y - 1, 62, 24, C.outline);
    rect(c, x, y, 60, 9, C.wood);
    rect(c, x, y, 60, 1, C.woodLight);
    rect(c, x, y + 9, 60, 13, C.woodSide);
    const drawerX = side === "worker" ? x + 42 : x + 4;
    rect(c, drawerX, y + 11, 14, 9, C.woodDark);
    rect(c, drawerX + 1, y + 12, 12, 7, C.woodSide);
    rect(c, drawerX + 6, y + 15, 3, 1, C.woodDark);
    rect(c, x + 1, y + 23, 3, 7, C.outline);
    rect(c, x + 56, y + 23, 3, 7, C.outline);
    rect(c, x + 2, y + 23, 1, 6, C.woodDark);
    rect(c, x + 57, y + 23, 1, 6, C.woodDark);
    c.fillStyle = "rgba(90, 50, 20, 0.22)";
    c.fillRect(x, y + 30, 60, 2);

    // monitor
    rect(c, cx - 15, 73, 30, 22, C.outline);
    rect(c, cx - 14, 74, 28, 20, C.metal);
    rect(c, cx - 14, 74, 28, 1, C.metalLight);
    rect(c, cx - 2, 95, 4, 2, C.metal);
    rect(c, cx - 6, 96, 12, 2, C.metalLight);
    // keyboard
    rect(c, cx - 10, 99, 20, 4, C.outline);
    rect(c, cx - 9, 99, 18, 3, C.plastic);
    for (let i = 0; i < 8; i++) rect(c, cx - 8 + i * 2, 100, 1, 1, C.plasticDark);

    // computer tower beside the desk
    const tx = side === "worker" ? x + 63 : x - 12;
    rect(c, tx, 100, 10, 24, C.outline);
    rect(c, tx + 1, 101, 8, 22, "#c9ccd6");
    rect(c, tx + 1, 101, 8, 1, "#e1e3ea");
    rect(c, tx + 2, 103, 6, 1, "#8a8d9a");
    rect(c, tx + 2, 105, 6, 1, "#8a8d9a");
    c.fillStyle = "rgba(90, 50, 20, 0.22)";
    c.fillRect(tx, 124, 10, 2);

    if (side === "worker") {
      rect(c, x + 47, 92, 5, 6, C.outline);
      rect(c, x + 48, 93, 3, 4, C.blue);
      rect(c, x + 52, 94, 1, 2, C.outline);
    } else {
      // stack of papers and a desk lamp
      rect(c, x + 6, 93, 12, 4, C.outline);
      rect(c, x + 7, 93, 10, 3, C.paper);
      rect(c, x + 8, 91, 10, 3, C.outline);
      rect(c, x + 9, 91, 8, 2, "#eeeae0");
      rect(c, x + 50, 80, 6, 3, C.outline);
      rect(c, x + 51, 80, 4, 2, C.red);
      rect(c, x + 53, 83, 1, 11, C.outline);
      rect(c, x + 50, 94, 7, 2, C.outline);
    }
  }

  function drawStatic(c) {
    drawWall(c);
    drawFloor(c);
    drawPicture(c, 30, 12);
    drawBookshelf(c, 106, 7);
    drawDoor(c, 146);
    drawNote(c, 183, 22);
    drawBookshelf(c, 198, 19);
    drawBoard(c, 240, 10);
    drawCooler(c, 296, 26);
    drawRug(c, 138, 118);
    drawBin(c, 46, 116);
    drawBin(c, 268, 118);
    drawCoffee(c, 12, 152);
    sprite(c, SPRITES.plant, 290, 152, {
      G: C.leaf, g: C.leafDark, L: C.leafLight, O: C.outline, P: C.pot, p: C.potDark,
    });
    for (const [name, agent] of Object.entries(AGENTS)) drawDesk(c, agent.cx, name);
  }

  // ---------- dynamic layer ----------

  const canvas = document.getElementById("scene");
  const ctx = canvas.getContext("2d");
  canvas.width = W;
  canvas.height = H;
  const background = document.createElement("canvas");
  background.width = W;
  background.height = H;
  drawStatic(background.getContext("2d"));

  let state = null;
  let frame = 0;
  let flight = null; // a sheet of paper flying between desks
  let celebrateUntil = 0;

  function screenRect(cx) {
    return { x: cx - 12, y: 76, w: 24, h: 16 };
  }

  function drawScreen(c, name, status) {
    const s = screenRect(AGENTS[name].cx);
    const scrolling = status === "working" || status === "reviewing";
    if (status === "approved") {
      rect(c, s.x, s.y, s.w, s.h, "#1f7a3a");
      sprite(c, SPRITES.check, s.x + 8, s.y + 4, { W: C.white });
      return;
    }
    if (status === "rejected") {
      rect(c, s.x, s.y, s.w, s.h, "#8a2430");
      sprite(c, SPRITES.cross, s.x + 9, s.y + 5, { W: C.white });
      return;
    }
    rect(c, s.x, s.y, s.w, s.h, C.screen);
    const code = ["#7aa2f7", "#9ece6a", "#e0af68", "#bb9af7", "#7dcfff", "#c0caf5"];
    const diff = ["#3fb950", "#6e7681", "#f85149", "#3fb950", "#6e7681", "#6e7681"];
    const palette = name === "worker" ? code : diff;
    const widths = [14, 9, 17, 6, 12, 15, 8, 11];
    const indents = [0, 2, 2, 4, 2, 0, 2, 4];
    const shift = scrolling ? Math.floor(frame / (name === "worker" ? 1 : 2)) : 0;
    c.save();
    c.beginPath();
    c.rect(s.x, s.y, s.w, s.h);
    c.clip();
    const alpha = scrolling ? 1 : 0.35;
    c.globalAlpha = alpha;
    for (let i = 0; i < 9; i++) {
      const k = (i + shift) % widths.length;
      rect(c, s.x + 2 + indents[k], s.y + 1 + i * 2, widths[k], 1, palette[k % palette.length]);
    }
    c.globalAlpha = 1;
    if (status === "working" && frame % 4 < 2) rect(c, s.x + 2 + 10, s.y + 15, 2, 1, C.white);
    if (status === "reviewing") {
      const t = (frame % 24) / 24;
      const lx = s.x + 1 + Math.round(Math.sin(t * Math.PI * 2) * 6 + 8);
      const ly = s.y + 2 + Math.round(Math.cos(t * Math.PI * 2) * 3 + 3);
      sprite(c, SPRITES.lens, lx, ly, { W: C.white, B: C.woodDark });
    }
    c.restore();
    // screen glare
    rect(c, s.x, s.y, s.w, 1, "rgba(255,255,255,0.08)");
  }

  function drawPerson(c, name, status) {
    const a = AGENTS[name];
    const cx = a.cx;
    const bob = status === "idle" && frame % 16 < 8 ? 1 : 0;
    const tilt = status === "reviewing" ? (frame % 12 < 6 ? -1 : 1) : 0;
    const celebrating = name === "reviewer" && status === "approved" && performance.now() < celebrateUntil;
    const shirt = { T: a.shirt, t: a.shirtDark };

    // arms
    if (celebrating) {
      const up = frame % 4 < 2 ? 0 : 1;
      rect(c, cx - 9, 89 + up, 2, 12, a.shirt);
      rect(c, cx + 7, 89 + up, 2, 12, a.shirt);
      rect(c, cx - 9, 87 + up, 2, 2, C.skin);
      rect(c, cx + 7, 87 + up, 2, 2, C.skin);
    } else {
      const typing = status === "working";
      const left = typing && frame % 2 === 0 ? 1 : 0;
      const right = typing && frame % 2 === 1 ? 1 : 0;
      rect(c, cx - 8, 100 + bob, 3, 4, a.shirt);
      rect(c, cx + 5, 100 + bob, 3, 4, a.shirt);
      rect(c, cx - 7, 99 - left + bob, 2, 2, C.skin);
      rect(c, cx + 5, 99 - right + bob, 2, 2, C.skin);
    }

    sprite(c, SPRITES.body, cx - 7, 101 + bob, shirt);
    const head = name === "worker" ? SPRITES.headWorker : SPRITES.headReviewer;
    const headY = (name === "worker" ? 93 : 92) + bob;
    sprite(c, head, cx - 5 + tilt, headY, { H: a.hair, h: a.hairLight, K: "#1b1d22", S: C.skin });

    sprite(c, SPRITES.chair, cx - 8, 107, { O: C.outline, L: C.chairLight, C: C.chair, D: C.chairDark });
    rect(c, cx - 1, 120, 3, 4, C.outline);
    rect(c, cx - 6, 124, 13, 2, C.outline);
    rect(c, cx - 6, 126, 2, 1, C.outline);
    rect(c, cx + 5, 126, 2, 1, C.outline);

    if (celebrating) {
      const sparkle = frame % 4;
      for (const [dx, dy] of [[-12, 86], [12, 84], [-14, 96], [14, 94]]) {
        if ((dx + dy + sparkle) % 3 === 0) rect(c, cx + dx, dy, 1, 1, C.yellow);
        else rect(c, cx + dx, dy, 1, 1, C.white);
      }
    }
  }

  function drawSteam(c, name, status) {
    if (status !== "idle") return;
    const x = AGENTS[name].cx - 30 + (name === "worker" ? 49 : 9);
    const y = name === "worker" ? 88 : 87;
    const phase = frame % 8;
    rect(c, x + (phase < 4 ? 0 : 1), y - Math.floor(phase / 2), 1, 1, "rgba(255,255,255,0.7)");
    rect(c, x + (phase < 4 ? 1 : 0), y - 2 - Math.floor(phase / 3), 1, 1, "rgba(255,255,255,0.5)");
  }

  function drawTowerLight(c, name, status) {
    const x = AGENTS[name].cx - 30 + (name === "worker" ? 63 : -12);
    const busy = status === "working" || status === "reviewing";
    rect(c, x + 3, 108, 2, 1, busy && frame % 2 ? C.green : "#2f6b3a");
  }

  function drawClock(c) {
    const x = 134;
    const y = 20;
    sprite(c, SPRITES.clock, x, y, { O: C.outline, W: C.white });
    const now = new Date();
    const hand = (angle, length, color) => {
      for (let r = 1; r <= length; r++) {
        rect(c, x + 4 + Math.round(Math.sin(angle) * r), y + 4 - Math.round(Math.cos(angle) * r), 1, 1, color);
      }
    };
    hand(((now.getHours() % 12) + now.getMinutes() / 60) / 12 * Math.PI * 2, 2, C.outline);
    hand(now.getMinutes() / 60 * Math.PI * 2, 3, C.outline);
    rect(c, x + 4, y + 4, 1, 1, C.red);
  }

  // A sign above the door that lights up while the autopilot runs.
  const GLYPHS = {
    A: [".X.", "X.X", "XXX", "X.X", "X.X"],
    U: ["X.X", "X.X", "X.X", "X.X", "XXX"],
    T: ["XXX", ".X.", ".X.", ".X.", ".X."],
    O: ["XXX", "X.X", "X.X", "X.X", "XXX"],
  };

  function drawSign(c) {
    const pilot = state?.autopilot;
    const running = pilot?.enabled && !pilot.halted;
    const halted = pilot?.enabled && pilot.halted;
    const x = 148;
    const y = 1;
    rect(c, x, y, 26, 8, C.outline);
    rect(c, x + 1, y + 1, 24, 6, running ? "#b32b3a" : halted ? "#5a3d1e" : "#3b3346");
    const lit = running ? (frame % 8 < 6 ? "#ffe066" : "#ffb84a") : halted ? "#e8a13a" : "#6d6478";
    let gx = x + 6;
    for (const letter of "AUTO") {
      sprite(c, GLYPHS[letter], gx, y + 2, { X: lit });
      gx += 4;
    }
    if (running) rect(c, x + 3, y + 3, 1, 1, frame % 4 < 2 ? "#ffe066" : "#b32b3a");
  }

  function drawBoardSticky(c) {
    if (!state || state.task === null) return;
    const worker = state.agents.worker.status;
    const reviewer = state.agents.reviewer.status;
    let column = 0;
    let color = C.yellow;
    if (reviewer === "approved") { column = 2; color = "#9be38f"; }
    else if (reviewer === "reviewing" || (worker === "idle" && reviewer !== "rejected")) column = 1;
    else if (reviewer === "rejected") color = "#f7a1a1";
    const x = 244 + column * 15;
    const y = 18;
    rect(c, x, y, 9, 8, color);
    rect(c, x + 1, y + 2, 6, 1, "rgba(0,0,0,0.25)");
    rect(c, x + 1, y + 4, 4, 1, "rgba(0,0,0,0.25)");
    rect(c, x + 3, y - 1, 2, 1, C.red);
  }

  function drawFlight(c) {
    if (!flight) return;
    const t = (performance.now() - flight.start) / flight.duration;
    if (t >= 1) {
      flight = null;
      return;
    }
    const x = flight.from + (flight.to - flight.from) * t;
    const y = 96 - Math.sin(t * Math.PI) * 26;
    // a soft shadow on the floor sells the height
    c.fillStyle = "rgba(90, 50, 20, 0.25)";
    c.fillRect(Math.round(x - 4), 134, 8, 2);
    sprite(c, SPRITES.paper, x - 5, y + (frame % 2), { O: C.outline, P: C.paper, d: flight.color });
  }

  function draw() {
    ctx.drawImage(background, 0, 0);
    drawClock(ctx);
    drawSign(ctx);
    drawBoardSticky(ctx);
    for (const name of Object.keys(AGENTS)) {
      const status = state ? state.agents[name].status : "idle";
      drawScreen(ctx, name, status);
      drawTowerLight(ctx, name, status);
      drawSteam(ctx, name, status);
      drawPerson(ctx, name, status);
    }
    drawFlight(ctx);
  }

  function fly(fromAgent, toAgent) {
    // Work going to review carries code lines; review findings coming back are red.
    const color = fromAgent === "reviewer" ? C.red : C.blue;
    flight = { from: AGENTS[fromAgent].cx, to: AGENTS[toAgent].cx, start: performance.now(), duration: 1800, color };
  }

  // ---------- sizing: fill the width, snapping to a whole-number scale when that costs little ----------

  const stage = document.getElementById("stage");
  function resize() {
    const box = stage.parentElement;
    const style = getComputedStyle(box);
    const available = box.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    let scale = available / W;
    const whole = Math.floor(scale);
    if (whole >= 2 && (scale - whole) / scale < 0.12) scale = whole;
    stage.style.width = `${W * scale}px`;
    stage.style.height = `${H * scale}px`;
    stage.style.setProperty("--px", `${scale}px`);
  }
  new ResizeObserver(resize).observe(stage.parentElement);
  resize();

  // Overlay elements (speech bubbles, name plates) are placed in scene coordinates.
  for (const [name, a] of Object.entries(AGENTS)) {
    const bubble = document.getElementById(`bubble-${name}`);
    const plate = document.getElementById(`plate-${name}`);
    bubble.style.left = `${(a.cx / W) * 100}%`;
    bubble.style.bottom = `${((H - 70) / H) * 100}%`;
    plate.style.left = `${(a.cx / W) * 100}%`;
    plate.style.top = `${(130 / H) * 100}%`;
  }

  // Clicking an agent's desk opens that agent's drawer.
  function agentAt(event) {
    const box = canvas.getBoundingClientRect();
    const x = ((event.clientX - box.left) / box.width) * W;
    const y = ((event.clientY - box.top) / box.height) * H;
    for (const [name, a] of Object.entries(AGENTS)) {
      if (Math.abs(x - a.cx) <= 34 && y >= 70 && y <= 132) return name;
    }
    return null;
  }
  canvas.addEventListener("click", (event) => {
    const agent = agentAt(event);
    if (agent) window.dispatchEvent(new CustomEvent("office:agent-click", { detail: { agent } }));
  });
  canvas.addEventListener("mousemove", (event) => {
    canvas.style.cursor = agentAt(event) ? "pointer" : "";
  });

  function drawPortrait(target, name) {
    const a = AGENTS[name];
    const c = target.getContext("2d");
    target.width = 20;
    target.height = 20;
    rect(c, 0, 0, 20, 20, name === "worker" ? "#cfe0fb" : "#e4d6fb");
    rect(c, 0, 15, 20, 5, C.chair);
    sprite(c, SPRITES.body, 3, 12, { T: a.shirt, t: a.shirtDark });
    const head = name === "worker" ? SPRITES.headWorker : SPRITES.headReviewer;
    sprite(c, head, 5, name === "worker" ? 4 : 3, { H: a.hair, h: a.hairLight, K: "#1b1d22", S: C.skin });
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reducedMotion) {
    setInterval(() => {
      frame++;
      draw();
    }, 1000 / FPS);
  }

  window.OfficeScene = {
    drawPortrait,
    setState(next) {
      const prev = state;
      state = next;
      if (prev) {
        const was = prev.agents;
        const now = next.agents;
        if (was.reviewer.status !== "reviewing" && now.reviewer.status === "reviewing") fly("worker", "reviewer");
        if (prev.verdict && !prev.verdict.sent && next.verdict && next.verdict.sent) fly("reviewer", "worker");
        if (was.reviewer.status !== "approved" && now.reviewer.status === "approved") celebrateUntil = performance.now() + 3000;
      }
      draw();
    },
  };
  draw();
})();
