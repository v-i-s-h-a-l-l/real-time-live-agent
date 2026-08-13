/** Route builders for curriculum navigation — keep IDs out of ad-hoc strings in UI. */

export function subjectPath(subjectId: string): string {
  return `/subjects/${encodeURIComponent(subjectId)}`;
}

export function chapterPath(subjectId: string, chapterId: string): string {
  return `${subjectPath(subjectId)}/chapters/${encodeURIComponent(chapterId)}`;
}

export function topicPath(
  subjectId: string,
  chapterId: string,
  topicId: string,
): string {
  return `${chapterPath(subjectId, chapterId)}/topics/${encodeURIComponent(topicId)}`;
}
