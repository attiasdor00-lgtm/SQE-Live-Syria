"""Render exact campaign diagrams used by the player manual.

The figures are generated from the authored topology, not from an illustrative
geographic guess.  They intentionally match the compact native Operations map.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont

from sqe.live.campaign32 import BLUE_GRID, FARPS, NEIGHBORS, RED_BASES, RED_ZONES


ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "docs" / "images" / "northern-watch"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BG = "#081422"
PANEL = "#102235"
GRID = "#334d65"
TEXT = "#e9f1fb"
MUTED = "#a9b9ca"
BLUE = "#35aef4"
BLUE_FILL = "#123d5c"
RED = "#ff7788"
RED_FILL = "#562a32"
GOLD = "#f0bb55"
GREEN = "#62d6a6"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def centered(draw, box, text, fill=TEXT, face=None):
    face = face or font(20, True)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=face)
    x = box[0] + (box[2] - box[0] - (right - left)) / 2
    y = box[1] + (box[3] - box[1] - (bottom - top)) / 2 - top
    draw.text((x, y), text, font=face, fill=fill)


def campaign_map(output: Path):
    image = Image.new("RGB", (1600, 1120), BG)
    d = ImageDraw.Draw(image)
    d.rectangle((0, 0, 1600, 8), fill=BLUE)
    d.text((42, 28), "NORTHERN WATCH  /  CAMPAIGN NETWORK", font=font(19, True), fill=BLUE)
    d.text((42, 68), "32 red sectors · linked front · physical FARP relays", font=font(38, True), fill=TEXT)
    d.text((42, 119), "Exact opening topology used by SQE Live 0.1.16. Connections are campaign links, not roads.",
           font=font(19), fill=MUTED)

    labels = {
        "negev": "NGV", "central": "CTR", "sharon": "SHR", "haifa": "HFA",
        "galilee": "GAL", "upper_galilee": "UGL", "golan": "GOL",
    }
    positions = dict(BLUE_GRID)
    owners = {zone: "blue" for zone in BLUE_GRID}
    names = {zone: labels[zone] for zone in BLUE_GRID}
    for row in RED_ZONES:
        zone_id, label, _, _, _, _, col, grid_row, *_ = row
        positions[zone_id] = (col, grid_row)
        owners[zone_id] = "red"
        names[zone_id] = label

    farp_zones = {zone for _, _, zone, _ in FARPS}
    base_zones = {"galilee", "central", "negev"} | {row[3] for row in RED_BASES}
    frontline = {
        zone for zone, links in NEIGHBORS.items()
        if any(owners[other] != owners[zone] for other in links)
    }

    ox, oy, sx, sy = 103, 210, 168, 83
    node_w, node_h = 104, 48

    def centre(zone):
        col, row = positions[zone]
        return ox + col * sx + node_w // 2, oy + row * sy + node_h // 2

    seen = set()
    for zone, links in NEIGHBORS.items():
        for other in links:
            key = tuple(sorted((zone, other)))
            if key in seen:
                continue
            seen.add(key)
            colour = GOLD if owners[zone] != owners[other] else GRID
            width = 7 if colour == GOLD else 3
            d.line((*centre(zone), *centre(other)), fill=colour, width=width)

    for zone, (col, row) in positions.items():
        x, y = ox + col * sx, oy + row * sy
        side = owners[zone]
        outline = GOLD if zone in frontline else BLUE if side == "blue" else RED
        fill = BLUE_FILL if side == "blue" else RED_FILL
        d.rounded_rectangle((x, y, x + node_w, y + node_h), radius=9, fill=fill, outline=outline,
                            width=4 if zone in frontline else 2)
        centered(d, (x, y, x + node_w, y + node_h), names[zone])
        flags = ("B" if zone in base_zones else "") + ("F" if zone in farp_zones else "")
        if flags:
            d.rounded_rectangle((x + node_w - 28, y - 10, x + node_w + 10, y + 12), radius=7,
                                fill=PANEL, outline=outline, width=2)
            centered(d, (x + node_w - 28, y - 10, x + node_w + 10, y + 12), flags,
                     fill=outline, face=font(12, True))

    d.rounded_rectangle((35, 973, 1565, 1082), radius=12, fill=PANEL, outline=GRID, width=2)
    legend = [(BLUE, "BLUE CONTROL"), (RED, "RED CONTROL"), (GOLD, "ACTIVE FRONT"),
              (TEXT, "B  AIRBASE"), (GREEN, "F  FARP RELAY")]
    x = 62
    for colour, text in legend:
        d.ellipse((x, 997, x + 16, 1013), fill=colour)
        d.text((x + 25, 991), text, font=font(16, True), fill=colour)
        x += 292
    d.text((62, 1035), "Initial mission fronts: Naqoura, Bint Jbeil and Quneitra. Capturing one sector exposes connected sectors.",
           font=font(17), fill=MUTED)
    image.save(output / "f10-map.png", optimize=True)


def zone_chain(output: Path):
    image = Image.new("RGB", (1600, 560), BG)
    d = ImageDraw.Draw(image)
    d.rectangle((0, 0, 1600, 8), fill=BLUE)
    d.text((42, 28), "ONE SECTOR  /  FOUR REQUIRED MISSIONS", font=font(19, True), fill=BLUE)
    d.text((42, 68), "A sector changes hands only after the chain and ground arrival", font=font(34, True), fill=TEXT)

    cards = [
        ("1", "SEAD", "Destroy every search\nand tracking radar", "SAM battery", BLUE),
        ("2", "DEAD", "Reduce the same SAM\nto 25% or less", "launchers + support", "#8ec8ff"),
        ("3", "STRIKE", "Reduce logistics / C2\nto 25% or less", "depot · fuel · command", GOLD),
        ("4", "CAS", "Destroy every vehicle\nin the garrison", "armour · IFV · SHORAD", RED),
        ("5", "CAPTURE", "Friendly assault column\nmust physically arrive", "ownership + FARP transfer", GREEN),
    ]
    left, top, width, gap = 32, 170, 280, 34
    for i, (number, title, objective, target, colour) in enumerate(cards):
        x = left + i * (width + gap)
        d.rounded_rectangle((x, top, x + width, 465), radius=14, fill=PANEL, outline=colour, width=3)
        d.ellipse((x + 18, top + 18, x + 64, top + 64), fill=colour)
        centered(d, (x + 18, top + 18, x + 64, top + 64), number, fill=BG, face=font(21, True))
        d.text((x + 78, top + 22), title, font=font(25, True), fill=colour)
        d.multiline_text((x + 18, top + 94), objective, font=font(20, True), fill=TEXT, spacing=6)
        d.line((x + 18, top + 178, x + width - 18, top + 178), fill=GRID, width=2)
        d.text((x + 18, top + 199), "TARGET", font=font(14, True), fill=MUTED)
        d.multiline_text((x + 18, top + 225), target, font=font(18), fill=MUTED, spacing=5)
        if i < len(cards) - 1:
            ax = x + width + 6
            d.line((ax, top + 147, ax + gap - 12, top + 147), fill=TEXT, width=3)
            d.polygon([(ax + gap - 12, top + 139), (ax + gap - 12, top + 155),
                       (ax + gap - 2, top + 147)], fill=TEXT)
    d.text((42, 510), "A red counterattack resets the captured sector to stage 1 and rebuilds its defensive chain.",
           font=font(19), fill=MUTED)
    image.save(output / "zone-chain.png", optimize=True)


def wrapped(draw, xy, text, width, size=18, fill=TEXT, bold=False, spacing=6):
    lines=[]
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, width=width) or [""])
    draw.multiline_text(xy, "\n".join(lines), font=font(size, bold), fill=fill, spacing=spacing)


def panel(draw, box, outline=GRID, fill=PANEL, radius=8, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def button(draw, box, text, active=False):
    panel(draw, box, outline=BLUE if active else GRID, fill="#1b3d58" if active else "#1b3044", radius=5, width=2)
    centered(draw, box, text, face=font(15, active))


def ui_base(title):
    image=Image.new("RGB",(1200,960),BG);d=ImageDraw.Draw(image)
    d.rectangle((0,0,1200,8),fill=BLUE)
    d.text((32,25),"NORTHERN WATCH  /  OPERATIONS UI",font=font(17,True),fill=BLUE)
    d.text((32,60),title,font=font(34,True),fill=TEXT)
    d.text((32,105),"Accurate 0.1.16 data preview. DCS fonts, skin and terrain are not loaded.",font=font(16),fill=MUTED)
    panel(d,(24,145,1176,925),outline=GRID,fill="#14283a",radius=10)
    tabs=[("Campaign",True),("Missions",False),("Resources",False),("Support",False)]
    x=40
    for name,active in tabs:
        button(d,(x,165,x+108,203),name,active);x+=116
    button(d,(965,165,1150,203),"Close  [Ctrl Shift Q]")
    return image,d


def campaign_ui(output: Path):
    image,d=ui_base("Campaign briefing")
    panel(d,(40,220,485,665));panel(d,(505,220,1150,665))
    left=("Operation Northern Watch\nLIVE / 00:00\n\nSITUATION\n"
          "Israel holds the blue rear area. Red forces hold 32 connected sectors across Lebanon and Syria. "
          "AI air and ground operations continue between player assignments.\n\n"
          "CAMPAIGN OBJECTIVE\nComplete each sector chain and help blue assault columns capture every red sector.\n\n"
          "Red sectors captured 0 / 32\nObjectives completed 0")
    wrapped(d,(55,238),left,43,17)
    right=("FLY THE CAMPAIGN\n\nOpen Missions, choose a frontline sector and review its current objective. "
           "Each red sector requires SEAD, DEAD, STRIKE and CAS, followed by physical ground arrival.\n\n"
           "F10 MAP\nBlue/red rings show control. Gold rings show the active front. Labels identify bases, airfields and FARPs; dashed lines show open supply corridors.\n\n"
           "YOUR ASSIGNMENT\nNo active assignment.\nSuggested mission: SEAD / Quneitra SA-6 battery\n\n"
           "ACTIVE FRONT\nNaqoura · Bint Jbeil · Quneitra")
    wrapped(d,(522,238),right,63,17)
    button(d,(40,685,485,728),"Select suggested task",True)
    panel(d,(40,748,485,895));wrapped(d,(55,765),"00:00  Operation Northern Watch begins.\nThe campaign clock follows this session.",43,16)
    panel(d,(505,685,1150,895));wrapped(d,(522,704),"LIVE  |  Saved at campaign 0 min\nSelect a sector or target; Accept assigns it.\nAutomatic checks recorded; DCS flight validation pending.",62,17)
    image.save(output/"ui-campaign.png",optimize=True)


def draw_mini_map(d, origin=(47,245)):
    labels={"negev":"NGV","central":"CTR","sharon":"SHR","haifa":"HFA","galilee":"GAL",
            "upper_galilee":"UGL","golan":"GOL"}
    pos=dict(BLUE_GRID);owners={z:"blue" for z in BLUE_GRID};names=dict(labels)
    for row in RED_ZONES:
        zid,label,_,_,_,_,col,r,*_=row;pos[zid]=(col,r);owners[zid]="red";names[zid]=label
    ox,oy=origin;sx,sy=48,36;w,h=39,22
    def c(z):
        col,row=pos[z];return ox+col*sx+w//2,oy+row*sy+h//2
    seen=set()
    for z,links in NEIGHBORS.items():
        for other in links:
            key=tuple(sorted((z,other)))
            if key in seen:continue
            seen.add(key);d.line((*c(z),*c(other)),fill=GOLD if owners[z]!=owners[other] else GRID,width=3 if owners[z]!=owners[other] else 1)
    for z,(col,row) in pos.items():
        x,y=ox+col*sx,oy+row*sy;colour=BLUE if owners[z]=="blue" else RED
        d.rounded_rectangle((x,y,x+w,y+h),radius=4,fill=BLUE_FILL if owners[z]=="blue" else RED_FILL,outline=colour,width=1)
        centered(d,(x,y,x+w,y+h),names[z],face=font(8,True))


def missions_ui(output: Path):
    image,d=ui_base("Selecting the opening SEAD mission")
    # Activate Missions tab visually.
    button(d,(40,165,148,203),"Campaign");button(d,(156,165,264,203),"Missions",True)
    panel(d,(40,220,485,630));draw_mini_map(d)
    d.text((54,574),"LIVE / 39-sector schematic",font=font(14,True),fill=MUTED)
    d.text((54,598),"* front  ·  B base  ·  F FARP",font=font(14),fill=MUTED)
    button(d,(505,220,1150,258),">  SEAD / Quneitra SA-6 battery",True)
    panel(d,(505,278,1150,650))
    detail=("SEAD / Quneitra SA-6 battery\nSector: Quneitra line\nStage: SEAD 1/4\nFormation: Syrian 1st Armoured Division battlegroup\n\n"
            "CAMPAIGN EFFECT\nDestroy every search/tracking radar. Surviving launchers become the DEAD objective; this does not capture the sector.\n\n"
            "SECTOR OBJECTIVE\nComplete SEAD to unlock DEAD, then STRIKE and CAS. A blue assault column must still arrive.")
    wrapped(d,(523,296),detail,62,17)
    button(d,(40,668,485,711),"Select suggested task",True)
    button(d,(505,668,640,711),"Accept task",True);button(d,(652,668,790,711),"Brief / coords");button(d,(802,668,940,711),"Mark on map")
    button(d,(952,668,1150,711),"Abort task")
    panel(d,(505,742,1150,895));wrapped(d,(523,760),"LIVE  |  Saved at campaign 0 min\nOnly the current stage is spawned. Completing it creates the next objective.",62,17)
    image.save(output/"ui-strike.png",optimize=True)


def support_ui(output: Path):
    image,d=ui_base("Requesting air support")
    button(d,(40,165,148,203),"Campaign");button(d,(156,165,264,203),"Missions")
    button(d,(272,165,390,203),"Resources");button(d,(398,165,506,203),"Support",True)
    panel(d,(40,220,485,665));panel(d,(505,220,1150,665))
    availability=("SUPPORT AVAILABILITY\nRequests support the accepted task.\n\nCAP / READY\n2 F-15C ready at Ramat David\nCost: 8 fuel / 8 ammo\n\n"
                  "ESCORT / READY\n2 F-15C ready at Ramat David\nCost: 8 fuel / 8 ammo\n\nSEAD / READY\n2 F-16C ready at Ramat David\nCost: 8 fuel / 12 ammo\n\nSTRIKE / READY\n2 F-16C ready at Ramat David")
    wrapped(d,(55,238),availability,43,17)
    selected=("SEAD / Quneitra SA-6 battery\nSector: Quneitra line · Stage 1/4\n\nCAMPAIGN EFFECT\nDestroy the search/tracking radar to unlock DEAD.\n\n"
              "COORDINATES\nObserved live radar position is shown after mission start.\n\nObjective: destroy all designated radar units.")
    wrapped(d,(522,238),selected,62,17)
    x=505
    for label in ("CAP","ESCORT","SEAD","STRIKE","AWACS","TANKER"):
        button(d,(x,685,x+96,726),label,active=label=="SEAD");x+=106
    button(d,(505,740,700,781),"Hold support");button(d,(712,740,907,781),"Push support");button(d,(919,740,1150,781),"Save campaign")
    panel(d,(505,802,1150,895));wrapped(d,(522,819),"LIVE  |  Saved at campaign 0 min\nSupport stock is finite; failed spawns spend nothing.",62,16)
    image.save(output/"ui-support.png",optimize=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    campaign_map(args.output)
    zone_chain(args.output)
    campaign_ui(args.output)
    missions_ui(args.output)
    support_ui(args.output)


if __name__ == "__main__":
    main()
