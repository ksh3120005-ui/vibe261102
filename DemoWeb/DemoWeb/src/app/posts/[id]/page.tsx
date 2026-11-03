import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Eye, MessageSquare } from "lucide-react";

import { CommentForm } from "@/components/comment-form";
import { DeletePostForm } from "@/components/delete-post-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { incrementViews } from "@/lib/db";
import { formatDate } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function PostPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const post = await incrementViews(Number(id));
  if (!post) notFound();

  const edited = post.updatedAt !== post.createdAt;

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild>
        <Link href="/">
          <ArrowLeft />
          목록으로
        </Link>
      </Button>

      <Card>
        <CardHeader className="gap-3">
          <div>
            <Badge variant={post.category === "공지" ? "default" : "secondary"}>
              {post.category}
            </Badge>
          </div>
          <CardTitle className="text-2xl leading-snug">{post.title}</CardTitle>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{post.author}</span>
            <span>
              {formatDate(post.createdAt)}
              {edited && " (수정됨)"}
            </span>
            <span className="flex items-center gap-1">
              <Eye className="size-3.5" />
              {post.views}
            </span>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="py-6">
          <div className="min-h-32 whitespace-pre-wrap break-words leading-relaxed">
            {post.content}
          </div>
        </CardContent>
        <CardFooter className="flex flex-wrap justify-end gap-2 border-t">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/posts/${post.id}/edit`}>수정</Link>
          </Button>
          <DeletePostForm postId={post.id} />
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquare className="size-4" />
            댓글 {post.comments.length}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {post.comments.length > 0 && (
            <ul className="space-y-4">
              {post.comments.map((c) => (
                <li key={c.id} className="rounded-md border bg-muted/30 p-3">
                  <div className="mb-1 flex items-center gap-2 text-sm">
                    <span className="font-medium">{c.author}</span>
                    <span className="text-xs text-muted-foreground">
                      {formatDate(c.createdAt)}
                    </span>
                  </div>
                  <p className="whitespace-pre-wrap break-words text-sm">{c.content}</p>
                </li>
              ))}
            </ul>
          )}
          <CommentForm postId={post.id} />
        </CardContent>
      </Card>
    </div>
  );
}
