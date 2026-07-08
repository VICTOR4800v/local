"""
Sfera olografica.

Il nucleo e' ora una sfera PIENA e uniforme (gradiente radiale simulato
con cerchi concentrici, piu' un riflesso per dare volume), che respira
lentamente in modo sempre costante — non reagisce mai alla voce.

Tutta la "reattivita' vocale" vive esclusivamente nell'alone di
particelle che orbitano attorno al nucleo (e nei piccoli impulsi che si
espandono verso l'esterno quando JARVIS parla): quando speaking=True le
particelle orbitano piu' veloci, si illuminano di piu' e compaiono
impulsi concentrici. Il nucleo resta sempre identico a se stesso.
"""
import tkinter as tk
import math
import random


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, int(c))):02x}" for c in rgb)


def _lerp_color(c1, c2, t):
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    return _rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


class HologramSphere(tk.Canvas):
    def __init__(self, master, size=340, color="#00F0FF", bg="#0a0a0a", **kwargs):
        super().__init__(master, width=size, height=size, bg=bg,
                          highlightthickness=0, **kwargs)
        self.size = size
        self.color = color
        self.bg_color = bg

        self.core_t = 0.0          # respiro del nucleo: sempre costante
        self.grid_rotation = 0.0   # rotazione lenta della "texture" superficiale
        self.orbit_phase = 0.0     # fase orbitale delle particelle esterne

        self.running = False
        self.speaking = False
        self.voice_level = 0.0
        self.voice_target = 0.0

        self.orbiters = self._generate_orbiters(30)
        self.ripples = []  # impulsi che si espandono quando parla

    def set_speaking(self, speaking: bool):
        self.speaking = speaking
        if not speaking:
            self.voice_target = 0.0

    # ------------------------------------------------------------- ciclo

    def start(self):
        self.running = True
        self._tick()

    def stop(self):
        self.running = False

    def _tick(self):
        if not self.running:
            return
        self._draw_frame()
        self.after(33, self._tick)

    # ------------------------------------------------------------- dati

    def _generate_orbiters(self, count):
        pts = []
        for k in range(count):
            pts.append({
                "angle0": 2 * math.pi * k / count + random.uniform(-0.05, 0.05),
                "tilt": random.uniform(0.30, 0.55),
                "radius_mult": random.uniform(1.22, 1.85),
                "speed": random.uniform(0.6, 1.3),
            })
        return pts

    def _update_voice_level(self):
        if self.speaking:
            if random.random() < 0.22:
                self.voice_target = random.uniform(0.2, 1.0)
        self.voice_level += (self.voice_target - self.voice_level) * 0.35

    # ------------------------------------------------------------- draw

    def _draw_frame(self):
        self.delete("all")
        self._update_voice_level()
        speak_boost = 1.0 if self.speaking else 0.0

        # Il nucleo respira SEMPRE alla stessa velocita', mai legato alla voce.
        self.core_t += 0.045
        core_pulse = 1.0 + 0.045 * math.sin(self.core_t)

        # Texture superficiale: rotazione lenta e costante (mai reattiva).
        self.grid_rotation += 0.012

        # Le particelle orbitanti invece accelerano e si illuminano parlando.
        self.orbit_phase += 0.012 + 0.10 * self.voice_level * speak_boost

        cx = cy = self.size / 2
        radius = self.size * 0.30 * core_pulse
        fov = 380

        self._draw_orbiters(cx, cy, radius, fov, back=True)
        self._draw_ripples(cx, cy, radius)
        self._draw_solid_core(cx, cy, radius)
        self._draw_surface_grid(cx, cy, radius)
        self._draw_orbiters(cx, cy, radius, fov, back=False)

        self._maybe_spawn_ripple(radius)

    def _draw_solid_core(self, cx, cy, radius):
        """Sfera piena e uniforme: gradiente radiale via cerchi concentrici + riflesso."""
        steps = 22
        edge_color = "#04202a"
        for i in range(steps, 0, -1):
            t = i / steps
            r = radius * t
            col = _lerp_color(self.color, edge_color, t ** 1.6)
            self.create_oval(cx - r, cy - r, cx + r, cy + r, outline="", fill=col)

        # riflesso per dare volume (effetto "sfera lucida")
        hl_r = radius * 0.32
        hl_x = cx - radius * 0.32
        hl_y = cy - radius * 0.38
        self.create_oval(hl_x - hl_r, hl_y - hl_r * 0.7, hl_x + hl_r, hl_y + hl_r * 0.7,
                          outline="", fill="#bffcff")

    def _draw_surface_grid(self, cx, cy, radius):
        """Un paio di meridiani sottili sopra la sfera, per l'effetto 'ologramma'."""
        for j in (0, 60, 120):
            rj = math.radians(j)
            segment = []
            for i in range(0, 361, 8):
                ri = math.radians(i)
                x = math.sin(rj) * math.cos(ri)
                y = math.sin(rj) * math.sin(ri)
                z = math.cos(rj)
                nx = x * math.cos(self.grid_rotation) - z * math.sin(self.grid_rotation)
                nz = x * math.sin(self.grid_rotation) + z * math.cos(self.grid_rotation)
                if nz < 0.02:  # nascondi la parte "dietro" la sfera
                    self._flush_segment(segment)
                    segment = []
                    continue
                segment.append((cx + nx * radius, cy + y * radius))
            self._flush_segment(segment)

    def _flush_segment(self, segment):
        if len(segment) > 1:
            flat = [c for pt in segment for c in pt]
            self.create_line(*flat, fill="#0d5866", width=1, smooth=True)

    def _draw_orbiters(self, cx, cy, radius, fov, back):
        boost = self.voice_level if self.speaking else 0.0
        ry = self.grid_rotation * 0.6  # leggera rotazione condivisa con la scena

        for o in self.orbiters:
            angle = o["angle0"] + self.orbit_phase * o["speed"]
            x = math.cos(angle)
            z = math.sin(angle) * math.cos(o["tilt"])
            y = math.sin(angle) * math.sin(o["tilt"])

            nx = x * math.cos(ry) - z * math.sin(ry)
            nz = x * math.sin(ry) + z * math.cos(ry)

            is_back = nz < 0
            if is_back != back:
                continue

            orb_radius = radius * o["radius_mult"] * (1.0 + 0.18 * boost)
            scale = fov / (fov + nz * 140)
            px = cx + nx * orb_radius * scale
            py = cy + y * orb_radius * scale

            r = max(1.2, 2.0 * scale) * (1.0 + 0.9 * boost)
            col = _lerp_color(self.color, "#ffffff", 0.35 * min(1.0, boost))
            self.create_oval(px - r, py - r, px + r, py + r, outline="", fill=col)

    def _maybe_spawn_ripple(self, radius):
        if self.speaking and self.voice_level > 0.45 and random.random() < 0.06:
            self.ripples.append({"r": radius * 1.05, "life": 1.0})

    def _draw_ripples(self, cx, cy, radius):
        alive = []
        for rp in self.ripples:
            rp["r"] += 2.4
            rp["life"] -= 0.03
            if rp["life"] > 0 and rp["r"] < radius * 2.4:
                col = _lerp_color(self.color, self.bg_color, 1.0 - rp["life"])
                self.create_oval(cx - rp["r"], cy - rp["r"], cx + rp["r"], cy + rp["r"],
                                  outline=col, width=1)
                alive.append(rp)
        self.ripples = alive