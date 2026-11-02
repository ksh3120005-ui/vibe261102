import tkinter as tk


class BlockBreaker:
    WIDTH = 800
    HEIGHT = 600
    BALL_RADIUS = 8
    PADDLE_WIDTH = 110
    PADDLE_HEIGHT = 14
    PADDLE_SPEED = 9

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("블럭깨기")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root,
            width=self.WIDTH,
            height=self.HEIGHT,
            background="#111827",
            highlightthickness=0,
        )
        self.canvas.pack()

        self.keys: set[str] = set()
        self.score = 0
        self.lives = 3
        self.state = "ready"
        self.bricks: dict[int, tuple[float, float, float, float]] = {}
        self.ball_velocity = [4.0, -5.0]

        self.score_text = self.canvas.create_text(
            24, 24, anchor="nw", fill="#f8fafc", font=("맑은 고딕", 14, "bold")
        )
        self.lives_text = self.canvas.create_text(
            self.WIDTH - 24,
            24,
            anchor="ne",
            fill="#f8fafc",
            font=("맑은 고딕", 14, "bold"),
        )
        self.message_text = self.canvas.create_text(
            self.WIDTH / 2,
            self.HEIGHT / 2,
            fill="#f8fafc",
            font=("맑은 고딕", 22, "bold"),
            justify="center",
        )
        self.canvas.create_text(
            self.WIDTH / 2,
            self.HEIGHT - 18,
            text="← → 이동   Space 시작/계속   P 일시정지   R 다시 시작",
            fill="#94a3b8",
            font=("맑은 고딕", 10),
        )

        self.paddle = self.canvas.create_rectangle(0, 0, 0, 0, fill="#38bdf8", outline="")
        self.ball = self.canvas.create_oval(0, 0, 0, 0, fill="#f8fafc", outline="")

        self.root.bind("<KeyPress>", self._key_down)
        self.root.bind("<KeyRelease>", self._key_up)
        self.root.focus_set()

        self._new_game()
        self.state = "ready"
        self._show_message("블럭깨기\n스페이스바를 눌러 시작")
        self._tick()

    def _new_game(self) -> None:
        self.score = 0
        self.lives = 3
        self.bricks.clear()
        self.canvas.delete("brick")

        colors = ["#fb7185", "#fb923c", "#facc15", "#4ade80", "#38bdf8"]
        columns = 10
        gap = 6
        brick_width = (self.WIDTH - 64 - gap * (columns - 1)) / columns
        brick_height = 22
        for row, color in enumerate(colors):
            for column in range(columns):
                left = 32 + column * (brick_width + gap)
                top = 82 + row * (brick_height + gap)
                brick = self.canvas.create_rectangle(
                    left,
                    top,
                    left + brick_width,
                    top + brick_height,
                    fill=color,
                    outline="",
                    tags="brick",
                )
                self.bricks[brick] = (left, top, left + brick_width, top + brick_height)

        paddle_y = self.HEIGHT - 58
        self.canvas.coords(
            self.paddle,
            (self.WIDTH - self.PADDLE_WIDTH) / 2,
            paddle_y,
            (self.WIDTH + self.PADDLE_WIDTH) / 2,
            paddle_y + self.PADDLE_HEIGHT,
        )
        self._reset_ball()
        self._update_hud()

    def _reset_ball(self) -> None:
        paddle_coords = self.canvas.coords(self.paddle)
        center_x = (paddle_coords[0] + paddle_coords[2]) / 2
        ball_y = paddle_coords[1] - self.BALL_RADIUS - 2
        self.canvas.coords(
            self.ball,
            center_x - self.BALL_RADIUS,
            ball_y - self.BALL_RADIUS,
            center_x + self.BALL_RADIUS,
            ball_y + self.BALL_RADIUS,
        )
        self.ball_velocity = [4.0, -5.0]

    def _key_down(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        self.keys.add(key)

        if key == "space":
            if self.state == "ready":
                self.state = "playing"
                self._show_message("")
            elif self.state == "paused":
                self.state = "playing"
                self._show_message("")
            elif self.state in {"won", "game_over"}:
                self._new_game()
                self.state = "playing"
                self._show_message("")
        elif key == "p" and self.state in {"playing", "paused"}:
            self.state = "paused" if self.state == "playing" else "playing"
            self._show_message("일시정지\nP 또는 Space를 눌러 계속" if self.state == "paused" else "")
        elif key == "r":
            self._new_game()
            self.state = "ready"
            self._show_message("스페이스바를 눌러 시작")

    def _key_up(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    def _tick(self) -> None:
        if self.state == "playing":
            self._move_paddle()
            self._move_ball()
        self.root.after(16, self._tick)

    def _move_paddle(self) -> None:
        dx = 0
        if "left" in self.keys or "a" in self.keys:
            dx -= self.PADDLE_SPEED
        if "right" in self.keys or "d" in self.keys:
            dx += self.PADDLE_SPEED

        left, _, right, _ = self.canvas.coords(self.paddle)
        dx = max(-left, min(dx, self.WIDTH - right))
        self.canvas.move(self.paddle, dx, 0)

    def _move_ball(self) -> None:
        previous = self.canvas.coords(self.ball)
        self.canvas.move(self.ball, *self.ball_velocity)
        left, top, right, bottom = self.canvas.coords(self.ball)

        if left <= 0 or right >= self.WIDTH:
            self.ball_velocity[0] *= -1
        if top <= 0:
            self.ball_velocity[1] = abs(self.ball_velocity[1])

        paddle_left, paddle_top, paddle_right, _ = self.canvas.coords(self.paddle)
        if (
            self.ball_velocity[1] > 0
            and bottom >= paddle_top
            and previous[3] <= paddle_top + self.PADDLE_HEIGHT
            and right >= paddle_left
            and left <= paddle_right
        ):
            hit_offset = ((left + right) / 2 - (paddle_left + paddle_right) / 2) / (
                self.PADDLE_WIDTH / 2
            )
            self.ball_velocity[0] = hit_offset * 6
            self.ball_velocity[1] = -max(4.0, 7.0 - abs(self.ball_velocity[0]) * 0.35)

        for brick, (brick_left, brick_top, brick_right, brick_bottom) in list(self.bricks.items()):
            if right >= brick_left and left <= brick_right and bottom >= brick_top and top <= brick_bottom:
                self.canvas.delete(brick)
                del self.bricks[brick]
                self.score += 10
                if previous[3] <= brick_top or previous[1] >= brick_bottom:
                    self.ball_velocity[1] *= -1
                else:
                    self.ball_velocity[0] *= -1
                self._update_hud()
                break

        if top > self.HEIGHT:
            self.lives -= 1
            self._update_hud()
            if self.lives <= 0:
                self.state = "game_over"
                self._show_message(f"게임 오버\n점수: {self.score}\nSpace 또는 R로 다시 시작")
            else:
                self._reset_ball()
                self.state = "ready"
                self._show_message("공을 놓쳤어요!\n스페이스바를 눌러 계속")
            return

        if not self.bricks:
            self.state = "won"
            self._show_message(f"모든 블럭을 깼어요!\n점수: {self.score}\nSpace 또는 R로 다시 시작")

    def _update_hud(self) -> None:
        self.canvas.itemconfigure(self.score_text, text=f"점수  {self.score}")
        self.canvas.itemconfigure(self.lives_text, text=f"남은 목숨  {self.lives}")

    def _show_message(self, message: str) -> None:
        self.canvas.itemconfigure(self.message_text, text=message)


if __name__ == "__main__":
    window = tk.Tk()
    BlockBreaker(window)
    window.mainloop()