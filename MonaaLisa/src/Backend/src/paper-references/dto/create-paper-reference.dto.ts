import { IsNotEmpty, IsString } from 'class-validator';

export class CreatePaperReferenceDto {
  @IsNotEmpty()
  @IsString()
  belonging_paper_entry_id!: string;

  @IsNotEmpty()
  @IsString()
  referenced_paper_entry_id!: string;
}

