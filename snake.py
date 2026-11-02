"""뱀 게임 (Snake Game) - tkinter 사용, 추가 설치 불필요

조작법:
  방향키 / WASD : 이동
  Space        : 일시정지 / 재개
  R            : 게임 오버 후 재시작
"""
import random
import tkinter as tk

CELL = 20          # 한 칸 크기(px)
COLS = 30          # 가로 칸 수
ROWS = 25          # 세로 칸 수
START_SPEED = 120  # 시작 속도 (ms, 작을수록 빠름)
MIN_SPEED = 50     # 최고 속도

BG = "#1e1e2e"
SNAKE_HEAD = "#a6e3a1"
SNAKE_BODY = "#40a02b"
FOOD = "#f38ba8"
TEXT = "#cdd6f4"

DIRECTIONS = {
    "Up": (0, -1), "w": (0, -1), "W": (0, -1),
    "Down": (0, 1), "s": (0, 1), "S": (0, 1),
    "Left": (-1, 0), "a": (-1, 0), "A": (-1, 0),
    "Right": (1, 0), "d": (1, 0), "D": (1, 0),
}


class SnakeGame:
    def __init__(self, root):
        self.root = root
        root.title("뱀 게임")
        root.resizable(False, False)

        self.score_label = tk.Label(root, font=("Consolas", 14), fg=TEXT, bg=BG, anchor="w")
        self.score_label.pack(fill="x")
        self.canvas = tk.Canvas(root, width=COLS * CELL, height=ROWS * CELL,
                                bg=BG, highlightthickness=0)
        self.canvas.pack()

        root.configure(bg=BG)
        root.bind("<Key>", self.on_key)

        self.high_score = 0
        self.after_id = None
        self.reset()

    def reset(self):
        cx, cy = COLS // 2, ROWS // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.score = 0
        self.speed = START_SPEED
        self.paused = False
        self.game_over = False
        self.food = self.place_food()
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.draw()
        self.tick()

    def place_food(self):
        free = [(x, y) for x in range(COLS) for y in range(ROWS) if (x, y) not in self.snake]
        return random.choice(free) if free else None

    def on_key(self, event):
        key = event.keysym
        if key in DIRECTIONS:
            dx, dy = DIRECTIONS[key]
            # 반대 방향으로는 바로 꺾을 수 없음
            if (dx, dy) != (-self.direction[0], -self.direction[1]):
                self.next_direction = (dx, dy)
        elif key == "space" and not self.game_over:
            self.paused = not self.paused
            self.draw()
        elif key in ("r", "R") and self.game_over:
            self.reset()

    def tick(self):
        if not self.paused and not self.game_over:
            self.step()
            self.draw()
        if not self.game_over:
            self.after_id = self.root.after(self.speed, self.tick)

    def step(self):
        self.direction = self.next_direction
        hx, hy = self.snake[0]
        new_head = (hx + self.direction[0], hy + self.direction[1])

        ate = new_head == self.food
        body = self.snake if ate else self.snake[:-1]  # 꼬리는 이번 턴에 빠지므로 제외

        x, y = new_head
        if not (0 <= x < COLS and 0 <= y < ROWS) or new_head in body:
            self.game_over = True
            self.high_score = max(self.high_score, self.score)
            return

        self.snake.insert(0, new_head)
        if ate:
            self.score += 10
            self.speed = max(MIN_SPEED, self.speed - 3)
            self.food = self.place_food()
            if self.food is None:  # 화면을 꽉 채움 = 승리
                self.game_over = True
                self.high_score = max(self.high_score, self.score)
        else:
            self.snake.pop()

    def draw_cell(self, pos, color, pad=1, oval=False):
        x, y = pos
        x1, y1 = x * CELL + pad, y * CELL + pad
        x2, y2 = (x + 1) * CELL - pad, (y + 1) * CELL - pad
        if oval:
            self.canvas.create_oval(x1, y1, x2, y2, fill=color, outline="")
        else:
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

    def draw(self):
        c = self.canvas
        c.delete("all")

        if self.food:
            self.draw_cell(self.food, FOOD, pad=3, oval=True)
        for i, seg in enumerate(self.snake):
            self.draw_cell(seg, SNAKE_HEAD if i == 0 else SNAKE_BODY)

        self.score_label.config(text=f"  점수: {self.score}    최고 점수: {self.high_score}")

        w, h = COLS * CELL, ROWS * CELL
        if self.paused:
            c.create_text(w / 2, h / 2, text="일시정지\n(Space로 재개)",
                          fill=TEXT, font=("Malgun Gothic", 20, "bold"), justify="center")
        if self.game_over:
            msg = "승리!" if self.food is None else "게임 오버"
            c.create_text(w / 2, h / 2 - 20, text=msg, fill=FOOD,
                          font=("Malgun Gothic", 28, "bold"))
            c.create_text(w / 2, h / 2 + 20, text=f"점수: {self.score}   R 키로 재시작",
                          fill=TEXT, font=("Malgun Gothic", 14))



def main():
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
