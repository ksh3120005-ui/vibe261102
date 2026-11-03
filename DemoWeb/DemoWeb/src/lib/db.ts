import "server-only";

import { createHash, randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";

import type { Category, Comment, Post, PublicPost } from "./types";

// 간단한 JSON 파일 저장소. 데모용이므로 실제 서비스에서는 DB로 교체하세요.
const DATA_DIR = path.join(process.cwd(), "data");
const DB_FILE = path.join(DATA_DIR, "db.json");

type Db = { nextId: number; posts: Post[] };

export function hashPassword(password: string) {
  return createHash("sha256").update(password).digest("hex");
}

function seed(): Db {
  const now = Date.now();
  const at = (minutesAgo: number) =>
    new Date(now - minutesAgo * 60_000).toISOString();
  const samples: Array<[Category, string, string, string]> = [
    ["공지", "게시판 이용 안내", "관리자", "DemoWeb 게시판에 오신 것을 환영합니다.\n\n글 작성 시 입력한 비밀번호로 수정·삭제할 수 있습니다. 서로 존중하는 커뮤니티를 만들어 주세요."],
    ["자유", "첫 번째 글입니다", "홍길동", "Next.js와 shadcn/ui로 만든 게시판이에요. 반갑습니다!"],
    ["질문", "Server Actions는 언제 쓰나요?", "김개발", "폼 제출 같은 데이터 변경 작업에 API 라우트 대신 써도 괜찮을까요?"],
    ["정보", "TypeScript 유틸리티 타입 정리", "이타입", "Partial, Pick, Omit, Record 등 자주 쓰는 유틸리티 타입을 정리했습니다."],
  ];
  const posts: Post[] = samples.map(([category, title, author, content], i) => ({
    id: i + 1,
    category,
    title,
    content,
    author,
    passwordHash: hashPassword("1234"),
    views: (samples.length - i) * 7,
    createdAt: at((samples.length - i) * 90),
    updatedAt: at((samples.length - i) * 90),
    comments: [],
  }));
  posts[2].comments.push({
    id: randomUUID(),
    author: "박리액트",
    content: "네, 폼 처리에는 Server Actions가 편리합니다.",
    createdAt: at(30),
  });
  return { nextId: posts.length + 1, posts };
}

async function readDb(): Promise<Db> {
  try {
    return JSON.parse(await fs.readFile(DB_FILE, "utf8")) as Db;
  } catch {
    const db = seed();
    await writeDb(db);
    return db;
  }
}

async function writeDb(db: Db) {
  await fs.mkdir(DATA_DIR, { recursive: true });
  await fs.writeFile(DB_FILE, JSON.stringify(db, null, 2), "utf8");
}

function toPublic(post: Post): PublicPost {
  const { passwordHash, ...rest } = post;
  void passwordHash;
  return rest;
}

export async function listPosts(opts: {
  q?: string;
  category?: string;
  page: number;
  pageSize: number;
}) {
  const { posts } = await readDb();
  const q = opts.q?.trim().toLowerCase();
  const filtered = posts
    .filter((p) => !opts.category || p.category === opts.category)
    .filter(
      (p) =>
        !q ||
        p.title.toLowerCase().includes(q) ||
        p.content.toLowerCase().includes(q) ||
        p.author.toLowerCase().includes(q),
    )
    .sort((a, b) => {
      // 공지는 항상 위로
      if (a.category === "공지" && b.category !== "공지") return -1;
      if (b.category === "공지" && a.category !== "공지") return 1;
      return b.id - a.id;
    });
  const totalPages = Math.max(1, Math.ceil(filtered.length / opts.pageSize));
  const page = Math.min(Math.max(1, opts.page), totalPages);
  const items = filtered
    .slice((page - 1) * opts.pageSize, page * opts.pageSize)
    .map(toPublic);
  return { items, total: filtered.length, page, totalPages };
}

export async function getPost(id: number) {
  const { posts } = await readDb();
  const post = posts.find((p) => p.id === id);
  return post ? toPublic(post) : null;
}

export async function incrementViews(id: number) {
  const db = await readDb();
  const post = db.posts.find((p) => p.id === id);
  if (!post) return null;
  post.views += 1;
  await writeDb(db);
  return toPublic(post);
}

export async function createPost(input: {
  category: Category;
  title: string;
  content: string;
  author: string;
  password: string;
}) {
  const db = await readDb();
  const now = new Date().toISOString();
  const post: Post = {
    id: db.nextId++,
    category: input.category,
    title: input.title,
    content: input.content,
    author: input.author,
    passwordHash: hashPassword(input.password),
    views: 0,
    createdAt: now,
    updatedAt: now,
    comments: [],
  };
  db.posts.push(post);
  await writeDb(db);
  return post.id;
}

/** 비밀번호가 맞으면 true, 틀리면 false, 글이 없으면 null */
export async function updatePost(
  id: number,
  password: string,
  input: { category: Category; title: string; content: string },
) {
  const db = await readDb();
  const post = db.posts.find((p) => p.id === id);
  if (!post) return null;
  if (post.passwordHash !== hashPassword(password)) return false;
  Object.assign(post, input, { updatedAt: new Date().toISOString() });
  await writeDb(db);
  return true;
}

/** 비밀번호가 맞으면 true, 틀리면 false, 글이 없으면 null */
export async function deletePost(id: number, password: string) {
  const db = await readDb();
  const index = db.posts.findIndex((p) => p.id === id);
  if (index === -1) return null;
  if (db.posts[index].passwordHash !== hashPassword(password)) return false;
  db.posts.splice(index, 1);
  await writeDb(db);
  return true;
}

export async function addComment(
  postId: number,
  input: { author: string; content: string },
) {
  const db = await readDb();
  const post = db.posts.find((p) => p.id === postId);
  if (!post) return false;
  const comment: Comment = {
    id: randomUUID(),
    author: input.author,
    content: input.content,
    createdAt: new Date().toISOString(),
  };
  post.comments.push(comment);
  await writeDb(db);
  return true;
}
