import { Type } from 'class-transformer';
import {
  IsIn,
  IsInt,
  IsISO8601,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
} from 'class-validator';

// Upper bound for one page of papers. The graph view asks for at most this many.
export const MAX_TAKE = 20000;
export const DEFAULT_TAKE = 100;

export const SORT_OPTIONS = [
  'published',
  'published_asc',
  'citations',
] as const;
export type PaperSort = (typeof SORT_OPTIONS)[number];

export class QueryPaperDto {
  // Free text, matched against title, authors and abstract (any of them)
  @IsOptional()
  @IsString()
  @MaxLength(300)
  search?: string;

  // Field searches from the advanced filter, combined with AND
  @IsOptional()
  @IsString()
  @MaxLength(300)
  title?: string;

  @IsOptional()
  @IsString()
  @MaxLength(300)
  author?: string;

  @IsOptional()
  @IsString()
  @MaxLength(300)
  abstract?: string;

  @IsOptional()
  @IsString()
  categories?: string;

  // Published-Zeitfenster (im Service in Date umwandeln)
  @IsOptional()
  @IsISO8601()
  dateFrom?: string;

  @IsOptional()
  @IsISO8601()
  dateTo?: string;

  // 'published' = newest first (default), 'published_asc' = oldest first,
  // 'citations' = most cited by arXiv papers first
  @IsOptional()
  @IsIn(SORT_OPTIONS)
  sort?: PaperSort;

  // Pagination
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(0)
  skip: number = 0;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(MAX_TAKE)
  take: number = DEFAULT_TAKE;
}
