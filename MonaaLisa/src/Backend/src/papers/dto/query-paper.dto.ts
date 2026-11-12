import { Type } from 'class-transformer';
import { IsInt, IsOptional, IsString, Min, IsISO8601 } from 'class-validator';

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
  take: number = 20;
}
