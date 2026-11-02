"""
제비우스 스타일 종스크롤 슈팅 게임 (pygame)

조작법
  방향키 / WASD : 이동
  Z / Space     : 공중 공격 (자퍼) - 누르고 있으면 연사
  X             : 지상 폭격 (블래스터) - 조준점 위치에 폭탄 투하
  P             : 일시정지
  M             : 효과음 켜기 / 끄기
  Enter         : 시작 / 재시작
  Esc           : 종료

공중의 적은 자퍼로, 지상의 적과 보스(거대 요새)는 블래스터로만 파괴할 수 있습니다.
적을 격추하면 가끔 P 아이템이 나오며, 먹을 때마다 자퍼 탄 수가 2 → 4 → 8 → 16발로 늘어납니다.
기체가 격추되면 한 단계 내려갑니다. 효과음은 외부 파일 없이 코드로 합성합니다.
"""
import math
import random
import sys
from array import array

import pygame

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 480, 720
FPS = 60
TILE = 40
SCROLL_SPEED = 1.2          # 지면 스크롤 속도 (px/frame)
SIGHT_DISTANCE = 170        # 기체와 폭격 조준점 사이 거리
BOSS_INTERVAL = 60 * 45     # 보스 등장까지 걸리는 프레임 수
POWER_SHOTS = (2, 4, 8, 16)                    # 파워 단계별 한 번에 나가는 탄 수
SHOT_SPREAD = {2: 0.0, 4: 0.2, 8: 0.5, 16: 0.9}  # 탄 수별 전체 부채꼴 각도 (라디안)

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
YELLOW = (255, 230, 90)
RED = (255, 60, 60)

GRASS, FOREST, WATER, ROAD, BRIDGE = range(5)


def dist(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# 효과음 (외부 파일 없이 파형을 직접 합성)
# ---------------------------------------------------------------------------
def synth(dur, f0, f1=None, wave='square', vol=0.5, noise=0.0, lowpass=1.0, decay=2.0):
    """주파수가 f0 -> f1로 변하는 파형을 만들어 [-1, 1] 범위의 샘플 목록으로 반환."""
    rate = pygame.mixer.get_init()[0]
    f1 = f0 if f1 is None else f1
    n = int(rate * dur)
    out = []
    phase = 0.0
    lp = 0.0
    for i in range(n):
        p = i / n
        phase += (f0 + (f1 - f0) * p) / rate
        ph = phase % 1.0
        if wave == 'square':
            v = 1.0 if ph < 0.5 else -1.0
        elif wave == 'triangle':
            v = 4.0 * abs(ph - 0.5) - 1.0
        else:
            v = math.sin(math.tau * ph)
        if noise:
            v = v * (1 - noise) + random.uniform(-1, 1) * noise
        lp += lowpass * (v - lp)  # 간단한 저역 통과 필터로 노이즈를 묵직하게
        attack = min(1.0, i / (rate * 0.003))  # 시작 순간의 '딱' 소리 방지
        out.append(lp * vol * attack * (1 - p) ** decay)
    return out


def melody(freqs, dur, wave='square', vol=0.5):
    out = []
    for f in freqs:
        out += synth(dur, f, wave=wave, vol=vol, decay=0.5)
    return out


class Sounds:
    def __init__(self):
        self.sounds = {}
        self.muted = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            pygame.mixer.set_num_channels(16)
            self._build()
        except pygame.error:
            self.sounds = {}  # 오디오 장치가 없으면 소리 없이 진행

    @staticmethod
    def _make(samples, volume):
        _, fmt, channels = pygame.mixer.get_init()
        if fmt != -16:
            raise pygame.error('16비트 오디오만 지원')
        buf = array('h')
        for s in samples:
            buf.extend([int(clamp(s, -1.0, 1.0) * 32767)] * channels)
        snd = pygame.mixer.Sound(buffer=buf.tobytes())
        snd.set_volume(volume)
        return snd

    def _build(self):
        m = self._make
        self.sounds = {
            'shot': m(synth(0.06, 1400, 700), 0.25),
            'bomb_drop': m(synth(0.45, 1000, 250, 'triangle', vol=0.6, decay=0.5), 0.4),
            'bomb_hit': m(synth(0.4, 90, 40, noise=0.85, lowpass=0.2, vol=1.0), 0.7),
            'explode': m(synth(0.3, 200, 60, noise=0.9, lowpass=0.35, vol=1.0), 0.5),
            'player_die': m(synth(1.1, 300, 30, noise=0.8, lowpass=0.12, vol=1.0, decay=1.2), 0.8),
            'block': m(synth(0.05, 2200, 1800, 'triangle'), 0.3),
            'boss_hit': m(synth(0.15, 320, 120, noise=0.3, vol=0.8), 0.6),
            'big_explode': m(synth(1.6, 120, 20, noise=0.9, lowpass=0.08, vol=1.0, decay=1.0), 0.9),
            'item': m(melody((880, 1320), 0.07), 0.4),
            'powerup': m(melody((523, 659, 784, 1047), 0.07), 0.45),
            'warning': m(melody((440, 660) * 4, 0.2, 'sine', 0.7), 0.5),
            'stage_clear': m(melody((523, 659, 784, 1047, 784, 1047), 0.12, 'triangle', 0.6), 0.5),
        }

    def play(self, name):
        if not self.muted and name in self.sounds:
            self.sounds[name].play()


# ---------------------------------------------------------------------------
# 지형 (절차적으로 생성되는 스크롤 배경)
# ---------------------------------------------------------------------------
class Terrain:
    def __init__(self):
        self.cols = WIDTH // TILE
        self.river_x = random.uniform(3, self.cols - 3)
        self.river_w = 2.2
        self.forest = [random.random() < 0.3 for _ in range(self.cols)]
        self.road_cd = random.randint(6, 14)
        self.rows = []  # [surface, y] 목록, 마지막 원소가 가장 위쪽 줄
        y = HEIGHT - TILE
        while y > -TILE * 2:
            self.rows.append([self._make_row(), y])
            y -= TILE

    def _make_row(self):
        # 강은 조금씩 구불구불하게 흐르고, 숲은 이전 줄을 이어받아 덩어리를 이룸
        self.river_x = clamp(self.river_x + random.uniform(-0.35, 0.35), 1.5, self.cols - 1.5)
        self.river_w = clamp(self.river_w + random.uniform(-0.15, 0.15), 1.4, 3.2)
        for i in range(self.cols):
            if random.random() < 0.12:
                self.forest[i] = not self.forest[i]
        self.road_cd -= 1
        is_road = self.road_cd <= 0
        if is_road:
            self.road_cd = random.randint(8, 16)

        surf = pygame.Surface((WIDTH, TILE))
        for c in range(self.cols):
            water = abs(c + 0.5 - self.river_x) < self.river_w / 2
            if is_road:
                kind = BRIDGE if water else ROAD
            elif water:
                kind = WATER
            elif self.forest[c]:
                kind = FOREST
            else:
                kind = GRASS
            self._draw_tile(surf, c * TILE, kind)
        return surf

    @staticmethod
    def _draw_tile(surf, x, kind):
        rect = pygame.Rect(x, 0, TILE, TILE)
        if kind == GRASS:
            surf.fill((78, 140, 70), rect)
            for _ in range(6):
                px, py = x + random.randint(2, TILE - 4), random.randint(2, TILE - 4)
                surf.fill((64, 120, 58), (px, py, 3, 3))
        elif kind == FOREST:
            surf.fill((40, 95, 45), rect)
            for _ in range(4):
                cx, cy = x + random.randint(10, 30), random.randint(10, 30)
                r = random.randint(7, 10)
                pygame.draw.circle(surf, (28, 78, 36), (cx, cy), r)
                pygame.draw.circle(surf, (58, 122, 58), (cx - 2, cy - 2), r // 2)
        elif kind == WATER:
            surf.fill((40, 90, 170), rect)
            for _ in range(2):
                px, py = x + random.randint(2, 24), random.randint(4, TILE - 4)
                pygame.draw.line(surf, (90, 140, 210), (px, py), (px + 12, py), 2)
        elif kind == ROAD:
            surf.fill((120, 115, 105), rect)
            pygame.draw.line(surf, (90, 86, 78), (x, 2), (x + TILE, 2), 2)
            pygame.draw.line(surf, (90, 86, 78), (x, TILE - 3), (x + TILE, TILE - 3), 2)
            surf.fill((210, 200, 120), (x + 12, TILE // 2 - 1, 16, 3))
        elif kind == BRIDGE:
            surf.fill((130, 95, 60), rect)
            for px in range(x, x + TILE, 8):
                pygame.draw.line(surf, (95, 68, 42), (px, 0), (px, TILE), 2)
            pygame.draw.line(surf, (70, 50, 30), (x, 1), (x + TILE, 1), 3)
            pygame.draw.line(surf, (70, 50, 30), (x, TILE - 2), (x + TILE, TILE - 2), 3)

    def update(self, speed):
        for row in self.rows:
            row[1] += speed
        self.rows = [r for r in self.rows if r[1] < HEIGHT]
        while self.rows[-1][1] > -TILE:
            self.rows.append([self._make_row(), self.rows[-1][1] - TILE])

    def draw(self, surf):
        for row_surf, y in self.rows:
            surf.blit(row_surf, (0, round(y)))


# ---------------------------------------------------------------------------
# 효과
# ---------------------------------------------------------------------------
class Explosion:
    def __init__(self, x, y, size=24, ground=False):
        self.x, self.y = x, y
        self.size = size
        self.ground = ground  # 지상 폭발은 지면과 함께 스크롤
        self.t = 0
        self.life = 26 + size // 3
        self.sparks = [(random.uniform(0, math.tau), random.uniform(1.5, 4) * size / 24)
                       for _ in range(10)]
        self.dead = False

    def update(self):
        self.t += 1
        if self.ground:
            self.y += SCROLL_SPEED
        if self.t >= self.life:
            self.dead = True

    def draw(self, surf):
        p = self.t / self.life
        x, y = int(self.x), int(self.y)
        r_outer = int(self.size * (0.4 + 0.8 * p))
        r_inner = int(self.size * 0.7 * (1 - p))
        pygame.draw.circle(surf, (255, int(160 * (1 - p)), 40), (x, y), r_outer,
                           max(1, int(4 * (1 - p)) + 1))
        if r_inner > 0:
            pygame.draw.circle(surf, (255, 240, 180), (x, y), r_inner)
        for a, s in self.sparks:
            d = s * self.t
            pygame.draw.circle(surf, (255, 200, 80),
                               (int(x + math.cos(a) * d), int(y + math.sin(a) * d)),
                               max(1, int(3 * (1 - p))))


class Crater:
    def __init__(self, x, y, r=12):
        self.x, self.y, self.r = x, y, r
        self.dead = False

    def update(self):
        self.y += SCROLL_SPEED
        if self.y > HEIGHT + 30:
            self.dead = True

    def draw(self, surf):
        r = self.r
        pygame.draw.ellipse(surf, (55, 48, 38), (self.x - r, self.y - r * 0.7, r * 2, r * 1.4))
        pygame.draw.ellipse(surf, (35, 30, 25), (self.x - r / 2, self.y - r * 0.35, r, r * 0.7))


# ---------------------------------------------------------------------------
# 플레이어
# ---------------------------------------------------------------------------
class Player:
    def __init__(self):
        self.x, self.y = WIDTH / 2, HEIGHT - 100
        self.speed = 4.5
        self.radius = 8
        self.shot_cd = 0
        self.invuln = 0
        self.alive = True

    def update(self, keys):
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if dx and dy:
            dx *= 0.7071
            dy *= 0.7071
        self.x = clamp(self.x + dx * self.speed, 20, WIDTH - 20)
        self.y = clamp(self.y + dy * self.speed, SIGHT_DISTANCE + 30, HEIGHT - 30)
        if self.shot_cd > 0:
            self.shot_cd -= 1
        if self.invuln > 0:
            self.invuln -= 1

    def sight(self):
        return self.x, self.y - SIGHT_DISTANCE

    def draw(self, surf, frame):
        if self.invuln and (self.invuln // 4) % 2:
            return  # 무적 시간 동안 깜빡임
        x, y = int(self.x), int(self.y)
        body = [(x, y - 22), (x + 7, y - 6), (x + 18, y + 10), (x + 18, y + 16), (x + 6, y + 12),
                (x, y + 16), (x - 6, y + 12), (x - 18, y + 16), (x - 18, y + 10), (x - 7, y - 6)]
        pygame.draw.polygon(surf, (220, 220, 232), body)
        pygame.draw.polygon(surf, (110, 110, 135), body, 2)
        pygame.draw.polygon(surf, (60, 140, 230), [(x, y - 12), (x + 4, y), (x, y + 4), (x - 4, y)])
        flame = 3 + (frame // 3) % 2
        pygame.draw.circle(surf, (255, 150, 40), (x - 6, y + 16), flame)
        pygame.draw.circle(surf, (255, 150, 40), (x + 6, y + 16), flame)


class PlayerBullet:
    def __init__(self, x, y, angle=0.0):
        self.x, self.y = x, y
        self.vx = math.sin(angle) * 12
        self.vy = -math.cos(angle) * 12
        self.radius = 4
        self.dead = False

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.y < -20 or self.x < -20 or self.x > WIDTH + 20:
            self.dead = True

    def draw(self, surf):
        head = (self.x, self.y)
        pygame.draw.line(surf, YELLOW, head, (self.x - self.vx, self.y - self.vy), 4)
        pygame.draw.line(surf, WHITE, head, (self.x - self.vx * 0.5, self.y - self.vy * 0.5), 2)


class PowerItem:
    """먹으면 자퍼 탄 수가 한 단계 늘어나는 P 아이템."""
    radius = 11
    label = None  # Game에서 폰트로 렌더링한 'P' 글자를 넣어둠

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.t = 0
        self.dead = False

    def update(self):
        self.t += 1
        self.y += 1.6
        self.x = clamp(self.x + math.sin(self.t * 0.08) * 1.2, 15, WIDTH - 15)
        if self.y > HEIGHT + 20:
            self.dead = True

    def draw(self, surf, frame):
        x, y = int(self.x), int(self.y)
        color = (60, 140, 255) if (frame // 8) % 2 else (255, 80, 80)
        pygame.draw.circle(surf, WHITE, (x, y), self.radius + 2)
        pygame.draw.circle(surf, color, (x, y), self.radius)
        if self.label:
            surf.blit(self.label, self.label.get_rect(center=(x, y)))


class Bomb:
    """조준점으로 날아가 지면에 떨어지는 폭탄. 목표 지점은 지면과 함께 스크롤된다."""

    def __init__(self, x, y, tx, ty):
        self.sx, self.sy = x, y - 10
        self.tx, self.ty = tx, ty
        self.t = 0
        self.duration = 28
        self.done = False

    def update(self):
        self.t += 1
        self.ty += SCROLL_SPEED
        if self.t >= self.duration:
            self.done = True

    def draw(self, surf):
        p = self.t / self.duration
        x = self.sx + (self.tx - self.sx) * p
        y = self.sy + (self.ty - self.sy) * p
        r = int(6 - 3 * p)
        pygame.draw.circle(surf, (255, 90, 70), (int(x), int(y)), r)
        pygame.draw.circle(surf, WHITE, (int(x), int(y)), max(1, r - 3))


class EnemyBullet:
    def __init__(self, x, y, angle, speed):
        self.x, self.y = x, y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.radius = 4
        self.dead = False

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if not (-10 < self.x < WIDTH + 10 and -10 < self.y < HEIGHT + 10):
            self.dead = True

    def draw(self, surf, frame):
        color = WHITE if (frame // 4) % 2 else (255, 140, 40)
        pygame.draw.circle(surf, (200, 40, 40), (int(self.x), int(self.y)), self.radius + 1)
        pygame.draw.circle(surf, color, (int(self.x), int(self.y)), self.radius - 1)


# ---------------------------------------------------------------------------
# 공중 적 (자퍼로 격추)
# ---------------------------------------------------------------------------
class AirEnemy:
    radius = 14
    hp = 1
    score = 30
    invincible = False

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.t = 0
        self.spin = random.uniform(0, math.tau)
        self.entered = False
        self.dead = False

    def update(self, game):
        self.t += 1
        self.move(game)
        if 0 <= self.y <= HEIGHT:
            self.entered = True
        offscreen = (self.y < -50 or self.y > HEIGHT + 50 or
                     self.x < -50 or self.x > WIDTH + 50)
        if (self.entered and offscreen) or self.t > FPS * 20:
            self.dead = True

    def move(self, game):
        pass


class Toroid(AirEnemy):
    """내려오다가 플레이어 반대쪽으로 급선회해 도망가는 회전 링."""
    score = 30

    def __init__(self, x, y, turn_y):
        super().__init__(x, y)
        self.turn_y = turn_y
        self.state = 0
        self.vx = self.vy = 0

    def move(self, game):
        self.spin += 0.25
        if self.state == 0:
            self.y += 3.2
            if self.y >= self.turn_y:
                self.state = 1
                self.vx = 3 if game.player.x < self.x else -3
                self.vy = 1.5
                if random.random() < 0.3 * game.difficulty:
                    game.fire_at(self.x, self.y)
        else:
            self.vy -= 0.12
            self.x += self.vx
            self.y += self.vy

    def draw(self, surf, frame):
        ow = 6 + 22 * abs(math.cos(self.spin))
        iw = ow * 0.45
        pygame.draw.ellipse(surf, (200, 200, 215), (self.x - ow / 2, self.y - 14, ow, 28))
        pygame.draw.ellipse(surf, (40, 40, 70), (self.x - iw / 2, self.y - 7, iw, 14))


class Torkan(AirEnemy):
    """내려와서 잠시 멈춰 조준탄을 쏘고 후퇴."""
    score = 50

    def __init__(self, x, y):
        super().__init__(x, y)
        self.stop_y = random.uniform(120, 320)
        self.state = 0
        self.timer = 0

    def move(self, game):
        if self.state == 0:
            self.y += 3
            if self.y >= self.stop_y:
                self.state = 1
        elif self.state == 1:
            self.timer += 1
            if self.timer == 25:
                game.fire_at(self.x, self.y + 10)
            if self.timer > 50:
                self.state = 2
        else:
            self.y -= 2.2

    def draw(self, surf, frame):
        x, y = self.x, self.y
        pts = [(x - 16, y - 8), (x + 16, y - 8), (x + 10, y + 8), (x, y + 14), (x - 10, y + 8)]
        pygame.draw.polygon(surf, (90, 170, 120), pts)
        pygame.draw.polygon(surf, (40, 90, 60), pts, 2)
        eye = RED if self.state == 1 and (frame // 4) % 2 else (150, 30, 30)
        pygame.draw.circle(surf, eye, (int(x), int(y)), 4)


class Zoshi(AirEnemy):
    """플레이어를 향해 일직선으로 돌진하는 회전 칼날."""
    radius = 12
    score = 70

    def __init__(self, x, y, target, speed):
        super().__init__(x, y)
        a = math.atan2(target[1] - y, target[0] - x)
        self.vx = math.cos(a) * speed
        self.vy = math.sin(a) * speed
        self.fired = False

    def move(self, game):
        self.spin += 0.3
        self.x += self.vx
        self.y += self.vy
        if not self.fired and self.t == 40:
            self.fired = True
            if random.random() < 0.4 * game.difficulty:
                game.fire_at(self.x, self.y)

    def draw(self, surf, frame):
        pts = []
        for i in range(8):
            a = self.spin + i * math.pi / 4
            r = 14 if i % 2 == 0 else 5
            pts.append((self.x + math.cos(a) * r, self.y + math.sin(a) * r))
        pygame.draw.polygon(surf, (220, 120, 200), pts)
        pygame.draw.polygon(surf, (120, 50, 110), pts, 2)


class Bacura(AirEnemy):
    """파괴할 수 없는 회전 금속판. 총알을 막아낸다."""
    radius = 15
    score = 0
    invincible = True

    def move(self, game):
        self.spin += 0.08
        self.y += 1.3

    def draw(self, surf, frame):
        h = max(3, 30 * abs(math.cos(self.spin)))
        rect = pygame.Rect(0, 0, 32, h)
        rect.center = (int(self.x), int(self.y))
        pygame.draw.rect(surf, (175, 145, 95), rect)
        pygame.draw.rect(surf, (100, 80, 50), rect, 2)
        if h > 10:
            pygame.draw.line(surf, (110, 90, 60), (rect.left + 4, rect.centery),
                             (rect.right - 4, rect.centery), 2)


# ---------------------------------------------------------------------------
# 지상 적 (블래스터로 폭격)
# ---------------------------------------------------------------------------
class GroundEnemy:
    radius = 16
    hp = 1
    score = 100

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.t = 0
        self.dead = False

    def update(self, game):
        self.t += 1
        self.y += SCROLL_SPEED
        if self.y > HEIGHT + 40:
            self.dead = True


class Barra(GroundEnemy):
    """움직이지 않는 피라미드형 기지."""
    score = 100

    def draw(self, surf, frame):
        x, y, r = int(self.x), int(self.y), 15
        pygame.draw.rect(surf, (155, 155, 160), (x - r, y - r, r * 2, r * 2))
        for cx, cy in ((x - r, y - r), (x + r, y - r), (x - r, y + r), (x + r, y + r)):
            pygame.draw.line(surf, (95, 95, 100), (cx, cy), (x, y), 2)
        pygame.draw.rect(surf, (80, 80, 85), (x - r, y - r, r * 2, r * 2), 2)
        pygame.draw.circle(surf, RED if (frame // 20) % 2 else (120, 30, 30), (x, y), 3)


class Logram(GroundEnemy):
    """주기적으로 뚜껑을 열고 조준탄을 쏘는 포대."""
    score = 300

    def __init__(self, x, y):
        super().__init__(x, y)
        self.fire_cd = random.randint(40, 120)

    def update(self, game):
        super().update(game)
        self.fire_cd -= 1
        if self.fire_cd <= 0:
            if 30 < self.y < HEIGHT - 160:
                game.fire_at(self.x, self.y)
            self.fire_cd = int(random.randint(90, 160) / game.difficulty)

    def draw(self, surf, frame):
        x, y = int(self.x), int(self.y)
        pygame.draw.circle(surf, (165, 135, 95), (x, y), 15)
        pygame.draw.circle(surf, (100, 80, 55), (x, y), 15, 2)
        opening = 7 if self.fire_cd < 20 else 3
        pygame.draw.circle(surf, (30, 25, 20), (x, y), opening)


class Grobda(GroundEnemy):
    """지상을 좌우로 달리는 전차. 폭탄이 떨어지면 피하려고 한다."""
    score = 200

    def __init__(self, x, y):
        super().__init__(x, y)
        self.vx = random.choice((-1, 1)) * random.uniform(0.6, 1.2)

    def update(self, game):
        super().update(game)
        self.x += self.vx
        bomb = game.bomb
        if bomb and abs(bomb.ty - self.y) < 60 and abs(bomb.tx - self.x) < 70:
            self.x += 1.6 if self.x >= bomb.tx else -1.6
        if self.x < 20 or self.x > WIDTH - 20:
            self.vx = -self.vx
            self.x = clamp(self.x, 20, WIDTH - 20)

    def draw(self, surf, frame):
        x, y = int(self.x), int(self.y)
        pygame.draw.rect(surf, (50, 55, 40), (x - 15, y - 13, 30, 6))
        pygame.draw.rect(surf, (50, 55, 40), (x - 15, y + 7, 30, 6))
        pygame.draw.rect(surf, (95, 115, 70), (x - 13, y - 9, 26, 18))
        pygame.draw.circle(surf, (70, 90, 55), (x, y), 7)
        direction = 1 if self.vx > 0 else -1
        pygame.draw.line(surf, (40, 45, 35), (x, y), (x + direction * 16, y), 3)


# ---------------------------------------------------------------------------
# 보스: 거대 공중 요새 (지상 높이로 낮게 떠 있어 블래스터로만 공격 가능)
# ---------------------------------------------------------------------------
class Boss:
    R = 120

    def __init__(self, stage):
        self.x, self.y = WIDTH / 2, -170
        self.stage = stage
        self.core_hp = 4 + stage * 2
        self.cannons = [{'dx': dx, 'dy': dy, 'alive': True, 'cd': random.randint(60, 120)}
                        for dx, dy in ((-70, -45), (70, -45), (-70, 50), (70, 50))]
        self.spread_cd = 120
        self.state = 'enter'
        self.timer = 0
        self.flash = 0
        self.defeated = False
        self.dead = False

    def update(self, game):
        self.timer += 1
        if self.flash:
            self.flash -= 1
        if self.state == 'enter':
            self.y += 1.5
            if self.y >= 230:
                self.state = 'fight'
                self.timer = 0
        elif self.state == 'fight':
            for c in self.cannons:
                if not c['alive']:
                    continue
                c['cd'] -= 1
                if c['cd'] <= 0:
                    game.fire_at(self.x + c['dx'], self.y + c['dy'], 3.2)
                    c['cd'] = random.randint(70, 130)
            self.spread_cd -= 1
            if self.spread_cd <= 0:
                for k in range(-2, 3):
                    game.fire_at(self.x, self.y, 3.0, offset=k * 0.22)
                self.spread_cd = max(80, 160 - self.stage * 10)
            if self.timer > FPS * 35:
                self.state = 'escape'  # 시간 안에 못 잡으면 도망감
        elif self.state == 'escape':
            self.y -= 2.5
            if self.y < -250:
                self.dead = True
        elif self.state == 'destroyed':
            self.y += SCROLL_SPEED
            if self.timer < 90 and self.timer % 6 == 0:
                game.explosions.append(Explosion(
                    self.x + random.uniform(-90, 90), self.y + random.uniform(-90, 90),
                    random.randint(20, 40), ground=True))
            if self.y > HEIGHT + 200:
                self.dead = True

    def targets(self):
        """폭격 가능한 지점 목록: (x, y, 판정 반경)"""
        if self.state not in ('enter', 'fight') or self.y < 0:
            return []
        pts = [(self.x + c['dx'], self.y + c['dy'], 18) for c in self.cannons if c['alive']]
        pts.append((self.x, self.y, 26))
        return pts

    def bomb_hit(self, bx, by, game):
        if self.state not in ('enter', 'fight') or self.y < 0:
            return 0
        for c in self.cannons:
            cx, cy = self.x + c['dx'], self.y + c['dy']
            if c['alive'] and dist(bx, by, cx, cy) < 18:
                c['alive'] = False
                game.explosions.append(Explosion(cx, cy, 30, ground=True))
                game.sounds.play('explode')
                game.spawn_item(cx, cy)  # 포대를 부수면 반드시 아이템
                return 1000
        if dist(bx, by, self.x, self.y) < 26:
            self.core_hp -= 1
            self.flash = 8
            if self.core_hp <= 0:
                self.state = 'destroyed'
                self.timer = 0
                self.defeated = True
                game.explosions.append(Explosion(self.x, self.y, 70, ground=True))
                game.sounds.play('big_explode')
                return 5000 * self.stage
            game.sounds.play('boss_hit')
            return 100
        return 0

    def draw(self, surf, frame):
        x, y, R = self.x, self.y, self.R
        outer = [(x + R * math.cos(math.pi / 8 + i * math.pi / 4),
                  y + R * math.sin(math.pi / 8 + i * math.pi / 4)) for i in range(8)]
        inner = [(x + (px - x) * 0.65, y + (py - y) * 0.65) for px, py in outer]
        dark = self.state == 'destroyed'
        pygame.draw.polygon(surf, (70, 70, 78) if dark else (115, 115, 130), outer)
        pygame.draw.polygon(surf, (55, 55, 65), outer, 4)
        pygame.draw.polygon(surf, (60, 60, 68) if dark else (92, 92, 108), inner)
        for (ox, oy), (ix, iy) in zip(outer, inner):
            pygame.draw.line(surf, (60, 60, 72), (ox, oy), (ix, iy), 3)
        # 테두리 신호등
        for i, (ox, oy) in enumerate(outer):
            if not dark and (frame // 10 + i) % 4 == 0:
                pygame.draw.circle(surf, (255, 220, 80), (int(x + (ox - x) * 0.85),
                                                          int(y + (oy - y) * 0.85)), 4)
        for c in self.cannons:
            cx, cy = int(x + c['dx']), int(y + c['dy'])
            if c['alive'] and not dark:
                pygame.draw.circle(surf, (70, 70, 82), (cx, cy), 13)
                pygame.draw.circle(surf, (20, 20, 25), (cx, cy), 6)
            else:
                pygame.draw.circle(surf, (40, 35, 30), (cx, cy), 11)
        if not dark:
            pulse = int(60 + 60 * math.sin(frame * 0.15))
            core = WHITE if self.flash else (220, pulse, pulse // 2)
            pygame.draw.circle(surf, (50, 50, 60), (int(x), int(y)), 28)
            pygame.draw.circle(surf, core, (int(x), int(y)), 22)


# ---------------------------------------------------------------------------
# 게임
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.font_big = pygame.font.SysFont('consolas', 44, bold=True)
        self.font = pygame.font.SysFont('consolas', 22, bold=True)
        self.font_small = pygame.font.SysFont('consolas', 16)
        PowerItem.label = self.font_small.render('P', True, WHITE)
        self.sounds = Sounds()
        self.hi_score = 0
        self.frame = 0
        self.terrain = Terrain()
        self.overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.overlay.fill((0, 0, 0, 150))
        self.reset()
        self.state = 'title'

    def reset(self):
        self.player = Player()
        self.player.invuln = 90
        self.bullets = []
        self.bomb = None
        self.enemy_bullets = []
        self.air = []
        self.ground = []
        self.explosions = []
        self.craters = []
        self.items = []
        self.power = 0  # POWER_SHOTS 인덱스
        self.kills_since_item = 0
        self.boss = None
        self.boss_timer = BOSS_INTERVAL
        self.score = 0
        self.lives = 3
        self.stage = 1
        self.air_cd = 90
        self.ground_cd = 60
        self.respawn_timer = 0
        self.banner_text = 'STAGE 1'
        self.banner_timer = 120
        self.state = 'play'

    @property
    def difficulty(self):
        return 1 + (self.stage - 1) * 0.3

    # ---- 입력 ----
    def on_key(self, key):
        if key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()
        if key == pygame.K_m:
            self.sounds.muted = not self.sounds.muted
            return
        if self.state in ('title', 'gameover'):
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.reset()
        elif self.state == 'play':
            if key == pygame.K_p:
                self.state = 'paused'
            elif key == pygame.K_x:
                self.drop_bomb()
        elif self.state == 'paused' and key == pygame.K_p:
            self.state = 'play'

    def drop_bomb(self):
        # 원작처럼 폭탄은 한 번에 하나만
        if self.bomb is None and self.player.alive:
            sx, sy = self.player.sight()
            self.bomb = Bomb(self.player.x, self.player.y, sx, sy)
            self.sounds.play('bomb_drop')

    # ---- 유틸 ----
    def fire_at(self, x, y, speed=3.5, offset=0.0):
        if not self.player.alive:
            return
        a = math.atan2(self.player.y - y, self.player.x - x) + offset
        speed *= min(1.6, 1 + (self.stage - 1) * 0.1)
        self.enemy_bullets.append(EnemyBullet(x, y, a, speed))

    def add_score(self, pts):
        self.score += pts
        self.hi_score = max(self.hi_score, self.score)

    def spawn_item(self, x, y):
        self.kills_since_item = 0
        self.items.append(PowerItem(x, y))

    def maybe_drop_item(self, x, y, chance):
        # 운이 나빠도 일정 수 이상 격추하면 반드시 아이템이 나오게 함
        self.kills_since_item += 1
        if random.random() < chance or self.kills_since_item >= 20:
            self.spawn_item(x, y)

    def pick_item(self):
        if self.power < len(POWER_SHOTS) - 1:
            self.power += 1
            self.banner_text = f'POWER UP x{POWER_SHOTS[self.power]}'
            self.banner_timer = 60
            self.sounds.play('powerup')
        else:
            self.add_score(1000)  # 최대 단계에서는 보너스 점수
            self.sounds.play('item')

    def fire_player_shots(self):
        p = self.player
        n = POWER_SHOTS[self.power]
        spread = SHOT_SPREAD[n]
        step = max(3, 24 / n)
        for i in range(n):
            k = i - (n - 1) / 2  # 가운데를 0으로 하는 좌우 대칭 인덱스
            self.bullets.append(PlayerBullet(p.x + k * step, p.y - 14, k * spread / (n - 1)))
        p.shot_cd = 7
        self.sounds.play('shot')

    def sight_locked(self):
        sx, sy = self.player.sight()
        for g in self.ground:
            if dist(sx, sy, g.x, g.y) < g.radius + 10:
                return True
        if self.boss:
            for tx, ty, r in self.boss.targets():
                if dist(sx, sy, tx, ty) < r:
                    return True
        return False

    # ---- 진행 ----
    def spawn(self):
        d = self.difficulty
        if self.boss is None:
            self.boss_timer -= 1
            if self.boss_timer <= 0:
                self.boss = Boss(self.stage)
                self.banner_text = 'WARNING'
                self.banner_timer = 150
                self.sounds.play('warning')

        self.air_cd -= 1
        if self.air_cd <= 0:
            r = random.random()
            if r < 0.35:
                x0 = random.uniform(60, WIDTH - 60)
                turn_y = random.uniform(140, 340)
                for i in range(4):
                    self.air.append(Toroid(x0, -20 - i * 40, turn_y))
            elif r < 0.55:
                self.air.append(Torkan(random.uniform(40, WIDTH - 40), -20))
            elif r < 0.85:
                x0 = random.uniform(60, WIDTH - 60)
                target = (self.player.x, self.player.y)
                for dx in (-25, 25):
                    self.air.append(Zoshi(x0 + dx, -20, target, 3.0 + 0.3 * d))
            else:
                self.air.append(Bacura(random.uniform(40, WIDTH - 40), -20))
            self.air_cd = int(random.randint(70, 130) / d)
            if self.boss:
                self.air_cd *= 2

        self.ground_cd -= 1
        if self.ground_cd <= 0:
            if self.boss is None:
                kind = random.choices((Barra, Logram, Grobda), weights=(40, 35, 25))[0]
                self.ground.append(kind(random.uniform(30, WIDTH - 30), -30))
            self.ground_cd = int(random.randint(50, 110) / d)

    def bomb_land(self, x, y):
        self.explosions.append(Explosion(x, y, 18, ground=True))
        self.craters.append(Crater(x, y, 10))
        self.sounds.play('bomb_hit')
        for g in self.ground:
            if not g.dead and dist(x, y, g.x, g.y) < g.radius + 12:
                g.hp -= 1
                if g.hp <= 0:
                    g.dead = True
                    self.add_score(g.score)
                    self.explosions.append(Explosion(g.x, g.y, 30, ground=True))
                    self.craters.append(Crater(g.x, g.y, 16))
                    self.maybe_drop_item(g.x, g.y, 0.12)
        if self.boss:
            self.add_score(self.boss.bomb_hit(x, y, self))

    def kill_player(self):
        p = self.player
        p.alive = False
        self.explosions.append(Explosion(p.x, p.y, 50))
        self.sounds.play('player_die')
        self.power = max(0, self.power - 1)
        self.lives -= 1
        self.respawn_timer = 100
        self.bomb = None

    def update(self, keys):
        self.frame += 1
        if self.state == 'paused':
            return
        self.terrain.update(SCROLL_SPEED)
        if self.state == 'title':
            return

        for obj in self.craters + self.explosions:
            obj.update()
        self.craters = [c for c in self.craters if not c.dead]
        self.explosions = [e for e in self.explosions if not e.dead]
        if self.state == 'gameover':
            return

        if self.banner_timer > 0:
            self.banner_timer -= 1

        # 플레이어
        p = self.player
        if p.alive:
            p.update(keys)
            if (keys[pygame.K_z] or keys[pygame.K_SPACE]) and p.shot_cd == 0:
                self.fire_player_shots()
        else:
            self.respawn_timer -= 1
            if self.respawn_timer <= 0:
                if self.lives > 0:
                    self.player = Player()
                    self.player.invuln = 120
                else:
                    self.state = 'gameover'
                    return

        self.spawn()

        for b in self.bullets:
            b.update()
        if self.bomb:
            self.bomb.update()
            if self.bomb.done:
                self.bomb_land(self.bomb.tx, self.bomb.ty)
                self.bomb = None
        for eb in self.enemy_bullets:
            eb.update()
        for it in self.items:
            it.update()
            if self.player.alive and dist(it.x, it.y, self.player.x, self.player.y) < it.radius + 14:
                it.dead = True
                self.pick_item()
        for e in self.air:
            e.update(self)
        for g in self.ground:
            g.update(self)
        if self.boss:
            self.boss.update(self)
            if self.boss.dead:
                if self.boss.defeated:
                    self.sounds.play('stage_clear')
                self.boss = None
                self.stage += 1
                self.boss_timer = BOSS_INTERVAL
                self.banner_text = f'STAGE {self.stage}'
                self.banner_timer = 120

        self.collide()

        self.bullets = [b for b in self.bullets if not b.dead]
        self.enemy_bullets = [b for b in self.enemy_bullets if not b.dead]
        self.items = [it for it in self.items if not it.dead]
        self.air = [e for e in self.air if not e.dead]
        self.ground = [g for g in self.ground if not g.dead]

    def collide(self):
        for b in self.bullets:
            for e in self.air:
                if e.dead or dist(b.x, b.y, e.x, e.y) > e.radius + b.radius:
                    continue
                b.dead = True
                if e.invincible:
                    self.explosions.append(Explosion(b.x, b.y, 6))
                    self.sounds.play('block')
                else:
                    e.hp -= 1
                    if e.hp <= 0:
                        e.dead = True
                        self.add_score(e.score)
                        self.explosions.append(Explosion(e.x, e.y, 24))
                        self.sounds.play('explode')
                        self.maybe_drop_item(e.x, e.y, 0.07)
                break

        p = self.player
        if not p.alive or p.invuln:
            return
        for eb in self.enemy_bullets:
            if dist(eb.x, eb.y, p.x, p.y) < eb.radius + p.radius:
                eb.dead = True
                self.kill_player()
                return
        for e in self.air:
            if not e.dead and dist(e.x, e.y, p.x, p.y) < e.radius + p.radius:
                if not e.invincible:
                    e.dead = True
                    self.explosions.append(Explosion(e.x, e.y, 24))
                    self.sounds.play('explode')
                self.kill_player()
                return

    # ---- 그리기 ----
    def draw_text(self, surf, text, font, color, center):
        img = font.render(text, True, color)
        surf.blit(img, img.get_rect(center=center))

    def draw_sight(self, surf):
        sx, sy = self.player.sight()
        color = RED if self.sight_locked() else (190, 255, 190)
        s, l = 12, 6
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            cx, cy = sx + dx * s, sy + dy * s
            pygame.draw.line(surf, color, (cx, cy), (cx - dx * l, cy), 2)
            pygame.draw.line(surf, color, (cx, cy), (cx, cy - dy * l), 2)
        pygame.draw.circle(surf, color, (int(sx), int(sy)), 2)

    def draw_hud(self, surf):
        surf.blit(self.font.render(f'SCORE {self.score}', True, WHITE), (10, 8))
        hi = self.font_small.render(f'HI {self.hi_score}', True, YELLOW)
        surf.blit(hi, hi.get_rect(midtop=(WIDTH // 2 + 40, 12)))
        st = self.font_small.render(f'STAGE {self.stage}', True, WHITE)
        surf.blit(st, st.get_rect(topright=(WIDTH - 10, 12)))
        for i in range(self.lives):
            x, y = 18 + i * 22, HEIGHT - 20
            pygame.draw.polygon(surf, (220, 220, 232),
                                [(x, y - 9), (x + 8, y + 6), (x, y + 3), (x - 8, y + 6)])
        shots = self.font_small.render(f'SHOT x{POWER_SHOTS[self.power]}', True, (120, 200, 255))
        surf.blit(shots, shots.get_rect(bottomright=(WIDTH - 10, HEIGHT - 10)))
        if self.sounds.muted:
            mute = self.font_small.render('MUTE', True, (200, 200, 200))
            surf.blit(mute, mute.get_rect(topright=(WIDTH - 10, 32)))

    def draw(self, surf):
        self.terrain.draw(surf)
        if self.state == 'title':
            surf.blit(self.overlay, (0, 0))
            self.draw_text(surf, 'SKY ZAPPER', self.font_big, YELLOW, (WIDTH // 2, 200))
            self.draw_text(surf, 'Xevious-style vertical shooter', self.font_small, WHITE,
                           (WIDTH // 2, 245))
            lines = ['ARROWS / WASD : MOVE', 'Z / SPACE : AIR SHOT', 'X : GROUND BOMB',
                     'P ITEM : SHOT 2 > 4 > 8 > 16', 'P : PAUSE   M : SOUND   ESC : QUIT']
            for i, line in enumerate(lines):
                self.draw_text(surf, line, self.font_small, (200, 200, 220),
                               (WIDTH // 2, 330 + i * 28))
            if (self.frame // 30) % 2:
                self.draw_text(surf, 'PRESS ENTER', self.font, WHITE, (WIDTH // 2, 520))
            return

        for c in self.craters:
            c.draw(surf)
        for g in self.ground:
            g.draw(surf, self.frame)
        if self.boss:
            self.boss.draw(surf, self.frame)
        if self.bomb:
            self.bomb.draw(surf)
        if self.player.alive and self.state != 'gameover':
            self.draw_sight(surf)
        for b in self.bullets:
            b.draw(surf)
        for e in self.air:
            e.draw(surf, self.frame)
        for it in self.items:
            it.draw(surf, self.frame)
        if self.player.alive and self.state != 'gameover':
            self.player.draw(surf, self.frame)
        for eb in self.enemy_bullets:
            eb.draw(surf, self.frame)
        for ex in self.explosions:
            ex.draw(surf)

        self.draw_hud(surf)

        if self.banner_timer > 0 and (self.banner_timer // 15) % 2 == 0:
            color = RED if self.banner_text == 'WARNING' else WHITE
            self.draw_text(surf, self.banner_text, self.font_big, color, (WIDTH // 2, HEIGHT // 2 - 60))

        if self.state == 'paused':
            surf.blit(self.overlay, (0, 0))
            self.draw_text(surf, 'PAUSED', self.font_big, WHITE, (WIDTH // 2, HEIGHT // 2))
        elif self.state == 'gameover':
            surf.blit(self.overlay, (0, 0))
            self.draw_text(surf, 'GAME OVER', self.font_big, RED, (WIDTH // 2, HEIGHT // 2 - 30))
            self.draw_text(surf, f'SCORE {self.score}', self.font, WHITE, (WIDTH // 2, HEIGHT // 2 + 20))
            if (self.frame // 30) % 2:
                self.draw_text(surf, 'PRESS ENTER', self.font, YELLOW, (WIDTH // 2, HEIGHT // 2 + 70))


def main():
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Sky Zapper - Xevious-style Shooter')
    clock = pygame.time.Clock()
    game = Game()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                game.on_key(event.key)
        game.update(pygame.key.get_pressed())
        game.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == '__main__':
    main()
