"use client";

import { useActionState, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { deletePostAction } from "@/lib/actions";
import type { FormState } from "@/lib/types";

export function DeletePostForm({ postId }: { postId: number }) {
  const [open, setOpen] = useState(false);
  const [state, formAction, pending] = useActionState(
    deletePostAction.bind(null, postId),
    {} as FormState,
  );

  if (!open) {
    return (
      <Button variant="destructive" size="sm" onClick={() => setOpen(true)}>
        삭제
      </Button>
    );
  }

  return (
    <form action={formAction} className="flex flex-wrap items-center gap-2">
      <Input
        name="password"
        type="password"
        placeholder="비밀번호"
        aria-label="삭제 비밀번호"
        className="h-8 w-36"
        autoFocus
        required
      />
      <Button type="submit" variant="destructive" size="sm" disabled={pending}>
        {pending ? "삭제 중..." : "삭제 확인"}
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
        취소
      </Button>
      {state.error && (
        <p className="w-full text-sm text-destructive" role="alert">
          {state.error}
        </p>
      )}
    </form>
  );
}
