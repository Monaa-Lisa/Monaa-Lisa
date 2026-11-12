import {
  IsISO8601,
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUrl,
} from 'class-validator';

export class CreatePaperDto {
  @IsNotEmpty()
  @IsString()
  entry_id!: string;

  @IsNotEmpty()
  @IsString()
  title!: string;

  @IsOptional()
  @IsString()
  authors?: string;

  @IsOptional()
  @IsString()
  abstract?: string;

  @IsOptional()
  @IsString()
  categories?: string;

  // ISO-8601 String; im Service in Date konvertieren
  @IsOptional()
  @IsISO8601()
  published?: string;

  @IsOptional()
  @IsISO8601()
  updated?: string;

  @IsOptional()
  @IsString()
  doi?: string;

  @IsOptional()
  @IsString()
  journal_ref?: string;

  @IsOptional()
  @IsString()
  license?: string;

  @IsOptional()
  @IsUrl()
  url?: string;

  @IsOptional()
  @IsString()
  s2_id?: string;

  @IsOptional()
  @IsInt()
  non_arxiv_citation_count?: number;

  @IsOptional()
  @IsInt()
  non_arxiv_reference_count?: number;

  @IsOptional()
  tsne?: unknown;
}
