import { ArrayMaxSize, IsArray, IsString } from 'class-validator';

// The frontend sends ids in chunks of 500, so 5000 leaves plenty of room.
export const MAX_BATCH_IDS = 5000;

export class BatchPapersDto {
  @IsArray()
  @ArrayMaxSize(MAX_BATCH_IDS)
  @IsString({ each: true })
  entryIds: string[] = [];
}
