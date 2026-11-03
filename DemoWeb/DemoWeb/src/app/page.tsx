import Link from "next/link";
import { MessageSquare, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listPosts } from "@/lib/db";
import { formatShortDate } from "@/lib/format";
import { CATEGORIES } from "@/lib/types";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 10;

type SearchParams = Promise<{ q?: string; category?: string; page?: string }>;

function buildHref(params: { q?: string; category?: string; page?: number }) {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.category) sp.set("category", params.category);
  if (params.page && params.page > 1) sp.set("page", String(params.page));
  const qs = sp.toString();
  return qs ? `/?${qs}` : "/";
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const { q = "", category = "", page: pageParam } = await searchParams;
  const { items, total, page, totalPages } = await listPosts({
    q,
    category,
    page: Number(pageParam) || 1,
    pageSize: PAGE_SIZE,
  });

  return (
    <Card>
      <CardHeader className="gap-4">
        <div className="flex items-end justify-between gap-2">
          <CardTitle className="text-xl">전체 게시글</CardTitle>
          <span className="text-sm text-muted-foreground">총 {total}개</span>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <nav className="flex flex-wrap gap-1" aria-label="카테고리">
            {["", ...CATEGORIES].map((c) => (
              <Button
                key={c || "all"}
                size="sm"
                variant={category === c ? "default" : "ghost"}
                asChild
              >
                <Link href={buildHref({ q, category: c })}>{c || "전체"}</Link>
              </Button>
            ))}
          </nav>

          <form action="/" className="flex gap-2">
            {category && <input type="hidden" name="category" value={category} />}
            <Input
              name="q"
              defaultValue={q}
              placeholder="제목·내용·작성자 검색"
              aria-label="검색어"
              className="sm:w-56"
            />
            <Button type="submit" size="icon" variant="outline" aria-label="검색">
              <Search />
            </Button>
          </form>
        </div>
      </CardHeader>

      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="hidden w-16 text-center sm:table-cell">번호</TableHead>
              <TableHead>제목</TableHead>
              <TableHead className="w-24">작성자</TableHead>
              <TableHead className="hidden w-24 text-center sm:table-cell">작성일</TableHead>
              <TableHead className="hidden w-16 text-center sm:table-cell">조회</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                  {q ? `"${q}"에 대한 검색 결과가 없습니다.` : "게시글이 없습니다."}
                </TableCell>
              </TableRow>
            ) : (
              items.map((post) => (
                <TableRow
                  key={post.id}
                  className={cn(post.category === "공지" && "bg-muted/50")}
                >
                  <TableCell className="hidden text-center text-muted-foreground sm:table-cell">
                    {post.id}
                  </TableCell>
                  <TableCell className="max-w-0 whitespace-normal sm:max-w-none">
                    <Link
                      href={`/posts/${post.id}`}
                      className="flex items-center gap-2 hover:underline"
                    >
                      <Badge
                        variant={post.category === "공지" ? "default" : "secondary"}
                        className="shrink-0"
                      >
                        {post.category}
                      </Badge>
                      <span className="truncate font-medium">{post.title}</span>
                      {post.commentCount > 0 && (
                        <span className="flex shrink-0 items-center gap-0.5 text-xs text-muted-foreground">
                          <MessageSquare className="size-3" />
                          {post.commentCount}
                        </span>
                      )}
                    </Link>
                  </TableCell>
                  <TableCell className="truncate">{post.author}</TableCell>
                  <TableCell className="hidden text-center text-muted-foreground sm:table-cell">
                    {formatShortDate(post.createdAt)}
                  </TableCell>
                  <TableCell className="hidden text-center text-muted-foreground sm:table-cell">
                    {post.views}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>

        {totalPages > 1 && (
          <nav className="mt-6 flex justify-center gap-1" aria-label="페이지">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <Button
                key={p}
                size="sm"
                variant={p === page ? "default" : "outline"}
                asChild
              >
                <Link href={buildHref({ q, category, page: p })}>{p}</Link>
              </Button>
            ))}
          </nav>
        )}
      </CardContent>
    </Card>
  );
}
