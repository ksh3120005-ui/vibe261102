export const CATEGORIES = ["자유", "질문", "정보", "공지"] as const;
export type Category = (typeof CATEGORIES)[number];

export type Comment = {
  id: string;
  author: string;
  content: string;
  createdAt: string;
};

export type Post = {
  id: number;
  category: Category;
  title: string;
  content: string;
  author: string;
  passwordHash: string;
  views: number;
  createdAt: string;
  updatedAt: string;
  comments: Comment[];
};

export type PublicPost = Omit<Post, "passwordHash">;

export type FormState = {
  error?: string;
};
