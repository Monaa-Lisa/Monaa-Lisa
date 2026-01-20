import {
  IsISO8601,
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
  summary?: string;

  // ISO-8601 String; im Service in Date konvertieren
  @IsOptional()
  @IsISO8601()
  published?: string;

  @IsOptional()
  @IsString()
  category?: string;

  @IsOptional()
  @IsUrl()
  url?: string;

  // unique
  @IsOptional()
  @IsString()
  hash?: string;

  @IsOptional()
  tsne?: unknown;
}
