import { Type } from 'class-transformer';
import {
  IsInt,
  IsISO8601,
  IsOptional,
  IsString,
  Max,
  Min,
} from 'class-validator';

// Upper bound for one page of papers. The graph view asks for at most this many.
export const MAX_TAKE = 20000;
export const DEFAULT_TAKE = 100;

export class QueryPaperDto {
  // Volltextsuche über title/authors/summary
  @IsOptional()
  @IsString()
  search?: string;

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

  // Sort order: 'published' (default) or 'citations' (most cited first)
  @IsOptional()
  @IsString()
  sort?: string;

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
