"use client";

import { useActionState, useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { addCommentAction } from "@/lib/actions";
import type { FormState } from "@/lib/types";

export function CommentForm({ postId }: { postId: number }) {
  const [state, formAction, pending] = useActionState(
    addCommentAction.bind(null, postId),
    {} as FormState,
  );
  const contentRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!pending && !state.error && contentRef.current) {
      contentRef.current.value = "";
    }
  }, [state, pending]);

  return (
    <form action={formAction} className="space-y-3">
      <Input
        name="author"
        maxLength={20}
        placeholder="작성자"
        aria-label="댓글 작성자"
        className="sm:max-w-48"
        required
      />
      <Textarea
        ref={contentRef}
        name="content"
        rows={3}
        maxLength={500}
        placeholder="댓글을 입력하세요"
        aria-label="댓글 내용"
        required
      />
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-destructive" role="alert">
          {state.error}
        </p>
        <Button type="submit" size="sm" disabled={pending}>
          {pending ? "등록 중..." : "댓글 등록"}
        </Button>
      </div>
    </form>
  );
}
