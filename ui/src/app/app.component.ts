import { Component } from '@angular/core';
import { RouterModule } from '@angular/router';
import { MessagesModule } from 'primeng/messages';
import { environment } from "../environments/environment";

@Component({
  standalone: true,
  imports: [RouterModule, MessagesModule],
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent {
  title = 'Geneweaver';
  version = environment.version;
}
