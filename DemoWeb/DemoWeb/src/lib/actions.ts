"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import * as db from "./db";
import { CATEGORIES, type Category, type FormState } from "./types";

function field(formData: FormData, name: string) {
  return String(formData.get(name) ?? "").trim();
}

function parsePostFields(formData: FormData) {
  const category = field(formData, "category") as Category;
  const title = field(formData, "title");
  const content = field(formData, "content");
  if (!CATEGORIES.includes(category)) return { error: "카테고리를 선택하세요." };
  if (!title) return { error: "제목을 입력하세요." };
  if (title.length > 100) return { error: "제목은 100자 이하로 입력하세요." };
  if (!content) return { error: "내용을 입력하세요." };
  return { data: { category, title, content } };
}

export async function createPostAction(
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const parsed = parsePostFields(formData);
  if (parsed.error) return { error: parsed.error };
  const author = field(formData, "author");
  const password = field(formData, "password");
  if (!author) return { error: "작성자를 입력하세요." };
  if (password.length < 4) return { error: "비밀번호는 4자 이상 입력하세요." };

  const id = await db.createPost({ ...parsed.data!, author, password });
  revalidatePath("/");
  redirect(`/posts/${id}`);
}

export async function updatePostAction(
  id: number,
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const parsed = parsePostFields(formData);
  if (parsed.error) return { error: parsed.error };

  const result = await db.updatePost(id, field(formData, "password"), parsed.data!);
  if (result === null) return { error: "게시글을 찾을 수 없습니다." };
  if (!result) return { error: "비밀번호가 일치하지 않습니다." };
  revalidatePath("/");
  revalidatePath(`/posts/${id}`);
  redirect(`/posts/${id}`);
}

export async function deletePostAction(
  id: number,
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const result = await db.deletePost(id, field(formData, "password"));
  if (result === null) return { error: "게시글을 찾을 수 없습니다." };
  if (!result) return { error: "비밀번호가 일치하지 않습니다." };
  revalidatePath("/");
  redirect("/");
}

export async function addCommentAction(
  postId: number,
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const author = field(formData, "author");
  const content = field(formData, "content");
  if (!author) return { error: "작성자를 입력하세요." };
  if (!content) return { error: "댓글 내용을 입력하세요." };
  if (content.length > 500) return { error: "댓글은 500자 이하로 입력하세요." };

  if (!(await db.addComment(postId, { author, content }))) {
    return { error: "게시글을 찾을 수 없습니다." };
  }
  revalidatePath(`/posts/${postId}`);
  return {};
}
