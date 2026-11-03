import "server-only";

import { createHash } from "node:crypto";

import { neon } from "@neondatabase/serverless";

import type { Category, PostSummary, PublicPost } from "./types";

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL 환경 변수가 설정되지 않았습니다. .env.local을 확인하세요.");
}

const sql = neon(process.env.DATABASE_URL);

export function hashPassword(password: string) {
  return createHash("sha256").update(password).digest("hex");
}

// 서버 프로세스당 한 번만 테이블 생성 + 샘플 데이터 삽입
let ready: Promise<void> | undefined;

function ensureSchema() {
  ready ??= (async () => {
    await sql`
      CREATE TABLE IF NOT EXISTS posts (
        id            SERIAL PRIMARY KEY,
        category      TEXT NOT NULL,
        title         TEXT NOT NULL,
        content       TEXT NOT NULL,
        author        TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        views         INTEGER NOT NULL DEFAULT 0,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
      )`;
    await sql`
      CREATE TABLE IF NOT EXISTS comments (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        post_id    INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
        author     TEXT NOT NULL,
        content    TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
      )`;
    await sql`CREATE INDEX IF NOT EXISTS comments_post_id_idx ON comments(post_id)`;

    const [{ count }] = await sql`SELECT count(*)::int AS count FROM posts`;
    if (count === 0) await seed();
  })().catch((err) => {
    ready = undefined; // 다음 요청에서 다시 시도
    throw err;
  });
  return ready;
}

async function seed() {
  const samples: Array<[Category, string, string, string, number]> = [
    ["공지", "게시판 이용 안내", "관리자", "DemoWeb 게시판에 오신 것을 환영합니다.\n\n글 작성 시 입력한 비밀번호로 수정·삭제할 수 있습니다. 서로 존중하는 커뮤니티를 만들어 주세요.", 28],
    ["자유", "첫 번째 글입니다", "홍길동", "Next.js와 shadcn/ui로 만든 게시판이에요. 반갑습니다!", 21],
    ["질문", "Server Actions는 언제 쓰나요?", "김개발", "폼 제출 같은 데이터 변경 작업에 API 라우트 대신 써도 괜찮을까요?", 14],
    ["정보", "TypeScript 유틸리티 타입 정리", "이타입", "Partial, Pick, Omit, Record 등 자주 쓰는 유틸리티 타입을 정리했습니다.", 7],
  ];
  const hash = hashPassword("1234");
  for (const [category, title, author, content, views] of samples) {
    const [{ id }] = await sql`
      INSERT INTO posts (category, title, content, author, password_hash, views)
      VALUES (${category}, ${title}, ${content}, ${author}, ${hash}, ${views})
      RETURNING id`;
    if (category === "질문") {
      await sql`
        INSERT INTO comments (post_id, author, content)
        VALUES (${id}, '박리액트', '네, 폼 처리에는 Server Actions가 편리합니다.')`;
    }
  }
}

const iso = (value: unknown) => new Date(value as string | Date).toISOString();

export async function listPosts(opts: {
  q?: string;
  category?: string;
  page: number;
  pageSize: number;
}) {
  await ensureSchema();
  const category = opts.category ?? "";
  const q = opts.q?.trim() ?? "";
  const like = `%${q.replace(/[\\%_]/g, "\\$&")}%`;

  const [{ total }] = await sql`
    SELECT count(*)::int AS total FROM posts
    WHERE (${category} = '' OR category = ${category})
      AND (${q} = '' OR title ILIKE ${like} OR content ILIKE ${like} OR author ILIKE ${like})`;

  const totalPages = Math.max(1, Math.ceil(total / opts.pageSize));
  const page = Math.min(Math.max(1, opts.page), totalPages);

  const rows = await sql`
    SELECT p.id, p.category, p.title, p.author, p.views, p.created_at, p.updated_at,
           (SELECT count(*)::int FROM comments c WHERE c.post_id = p.id) AS comment_count
    FROM posts p
    WHERE (${category} = '' OR p.category = ${category})
      AND (${q} = '' OR p.title ILIKE ${like} OR p.content ILIKE ${like} OR p.author ILIKE ${like})
    ORDER BY (p.category = '공지') DESC, p.id DESC
    LIMIT ${opts.pageSize} OFFSET ${(page - 1) * opts.pageSize}`;

  const items: PostSummary[] = rows.map((r) => ({
    id: r.id,
    category: r.category,
    title: r.title,
    author: r.author,
    views: r.views,
    createdAt: iso(r.created_at),
    updatedAt: iso(r.updated_at),
    commentCount: r.comment_count,
  }));
  return { items, total, page, totalPages };
}

async function loadPost(id: number, incrementViews: boolean) {
  await ensureSchema();
  if (!Number.isInteger(id)) return null;
  const [post] = incrementViews
    ? await sql`UPDATE posts SET views = views + 1 WHERE id = ${id} RETURNING *`
    : await sql`SELECT * FROM posts WHERE id = ${id}`;
  if (!post) return null;
  const comments = await sql`
    SELECT id, author, content, created_at FROM comments
    WHERE post_id = ${id} ORDER BY created_at`;
  const result: PublicPost = {
    id: post.id,
    category: post.category,
    title: post.title,
    content: post.content,
    author: post.author,
    views: post.views,
    createdAt: iso(post.created_at),
    updatedAt: iso(post.updated_at),
    comments: comments.map((c) => ({
      id: c.id,
      author: c.author,
      content: c.content,
      createdAt: iso(c.created_at),
    })),
  };
  return result;
}

export function getPost(id: number) {
  return loadPost(id, false);
}

export function incrementViews(id: number) {
  return loadPost(id, true);
}

export async function createPost(input: {
  category: Category;
  title: string;
  content: string;
  author: string;
  password: string;
}) {
  await ensureSchema();
  const [{ id }] = await sql`
    INSERT INTO posts (category, title, content, author, password_hash)
    VALUES (${input.category}, ${input.title}, ${input.content}, ${input.author},
            ${hashPassword(input.password)})
    RETURNING id`;
  return id as number;
}

async function checkPassword(id: number, password: string) {
  const [row] = await sql`SELECT password_hash FROM posts WHERE id = ${id}`;
  if (!row) return null;
  return row.password_hash === hashPassword(password);
}

/** 비밀번호가 맞으면 true, 틀리면 false, 글이 없으면 null */
export async function updatePost(
  id: number,
  password: string,
  input: { category: Category; title: string; content: string },
) {
  await ensureSchema();
  const ok = await checkPassword(id, password);
  if (!ok) return ok;
  await sql`
    UPDATE posts
    SET category = ${input.category}, title = ${input.title},
        content = ${input.content}, updated_at = now()
    WHERE id = ${id}`;
  return true;
}

/** 비밀번호가 맞으면 true, 틀리면 false, 글이 없으면 null */
export async function deletePost(id: number, password: string) {
  await ensureSchema();
  const ok = await checkPassword(id, password);
  if (!ok) return ok;
  await sql`DELETE FROM posts WHERE id = ${id}`;
  return true;
}

export async function addComment(
  postId: number,
  input: { author: string; content: string },
) {
  await ensureSchema();
  const rows = await sql`
    INSERT INTO comments (post_id, author, content)
    SELECT id, ${input.author}, ${input.content} FROM posts WHERE id = ${postId}
    RETURNING id`;
  return rows.length > 0;
}
