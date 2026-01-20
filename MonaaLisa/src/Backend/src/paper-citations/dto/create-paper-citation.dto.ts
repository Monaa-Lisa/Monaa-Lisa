import { IsNotEmpty, IsString } from 'class-validator';

export class CreatePaperCitationDto {
  @IsNotEmpty()
  @IsString()
  belonging_paper_entry_id!: string;

  @IsNotEmpty()
  @IsString()
  cited_paper_entry_id!: string;
}

