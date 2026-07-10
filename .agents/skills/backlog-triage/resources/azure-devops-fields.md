# Azure DevOps work-item import contract

Import an Azure DevOps 7.1 **Get Work Items Batch** response. Run WIQL first
to obtain work-item IDs, then fetch those IDs in batches of at most 200 with
the requested fields. WIQL returns IDs, not complete work-item records.

Use reference names, never display labels. The project process can omit
optional fields; the importer records those as `NULL` rather than guessing a
custom-field name.

| Local column | Azure DevOps reference name | Required | Notes |
| --- | --- | --- | --- |
| `azure_id` | `System.Id` | yes | Falls back to the REST record's `id`. |
| `title` | `System.Title` | yes | |
| `work_item_type` | `System.WorkItemType` | yes | |
| `state` | `System.State` | yes | State names vary by process. |
| `reason` | `System.Reason` | no | |
| `team_project` | `System.TeamProject` | no | |
| `area_path` | `System.AreaPath` | no | |
| `iteration_path` | `System.IterationPath` | no | |
| `tags` | `System.Tags` | no | Semicolon-delimited plain text. |
| `description` | `System.Description` | no | HTML is converted to text for search. |
| `acceptance_criteria` | `Microsoft.VSTS.Common.AcceptanceCriteria` | no | Available only on applicable work-item types. |
| `repro_steps` | `Microsoft.VSTS.TCM.ReproSteps` | no | Bug-specific. |
| `assigned_to` | `System.AssignedTo` | no | REST can return an identity object. |
| `created_at` | `System.CreatedDate` | no | |
| `changed_at` | `System.ChangedDate` | no | |
| `priority` | `Microsoft.VSTS.Common.Priority` | no | Business priority; lower numbers sort first. |
| `backlog_rank` | `Microsoft.VSTS.Common.BacklogPriority` | no | Scrum ordering field, not business priority. |
| `stack_rank` | `Microsoft.VSTS.Common.StackRank` | no | Agile/Basic/CMMI ordering field, not business priority. |
| `severity` | `Microsoft.VSTS.Common.Severity` | no | Available on applicable work-item types. |

Use this field list for the batch request:

```json
{
  "ids": [123, 456],
  "fields": [
    "System.Id",
    "System.Title",
    "System.WorkItemType",
    "System.State",
    "System.Reason",
    "System.TeamProject",
    "System.AreaPath",
    "System.IterationPath",
    "System.Tags",
    "System.Description",
    "Microsoft.VSTS.Common.AcceptanceCriteria",
    "Microsoft.VSTS.TCM.ReproSteps",
    "System.AssignedTo",
    "System.CreatedDate",
    "System.ChangedDate",
    "Microsoft.VSTS.Common.Priority",
    "Microsoft.VSTS.Common.BacklogPriority",
    "Microsoft.VSTS.Common.StackRank",
    "Microsoft.VSTS.Common.Severity"
  ]
}
```

Sources:

- [WIQL syntax and its ID-only result contract](https://learn.microsoft.com/en-us/azure/devops/boards/queries/wiql-syntax?view=azure-devops)
- [Get Work Items Batch 7.1](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/get-work-items-batch?view=azure-devops-rest-7.1)
- [Field reference-name conventions](https://learn.microsoft.com/en-us/azure/devops/organizations/settings/naming-restrictions?view=azure-devops)
- [Priority and ranking fields](https://learn.microsoft.com/en-us/azure/devops/boards/queries/planning-ranking-priorities?view=azure-devops)
