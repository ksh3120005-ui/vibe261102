"use client";

import Link from "next/link";
import { useActionState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { CATEGORIES, type FormState, type PublicPost } from "@/lib/types";

type Props = {
  action: (prev: FormState, formData: FormData) => Promise<FormState>;
  post?: PublicPost;
  cancelHref: string;
};

export function PostForm({ action, post, cancelHref }: Props) {
  const [state, formAction, pending] = useActionState(action, {});
  const isEdit = Boolean(post);

  return (
    <form action={formAction} className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-[180px_1fr]">
        <div className="space-y-2">
          <Label htmlFor="category">카테고리</Label>
          <Select name="category" defaultValue={post?.category ?? "자유"}>
            <SelectTrigger id="category" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="title">제목</Label>
          <Input
            id="title"
            name="title"
            maxLength={100}
            defaultValue={post?.title}
            placeholder="제목을 입력하세요"
            required
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="content">내용</Label>
        <Textarea
          id="content"
          name="content"
          rows={12}
          defaultValue={post?.content}
          placeholder="내용을 입력하세요"
          required
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="author">작성자</Label>
          <Input
            id="author"
            name="author"
            maxLength={20}
            defaultValue={post?.author}
            disabled={isEdit}
            placeholder="닉네임"
            required={!isEdit}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">비밀번호</Label>
          <Input
            id="password"
            name="password"
            type="password"
            minLength={isEdit ? undefined : 4}
            placeholder={isEdit ? "작성 시 입력한 비밀번호" : "수정·삭제 시 필요 (4자 이상)"}
            required
          />
        </div>
      </div>

      {state.error && (
        <p className="text-sm text-destructive" role="alert">
          {state.error}
        </p>
      )}

      <div className="flex justify-end gap-2">
        <Button variant="outline" asChild>
          <Link href={cancelHref}>취소</Link>
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? "저장 중..." : isEdit ? "수정하기" : "등록하기"}
        </Button>
      </div>
    </form>
  );
}
