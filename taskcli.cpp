#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <ctime>

using namespace std;

struct Task {
    int id;
    string description;
    string status;
    string createdAt;
    string updatedAt;
};

// ----------------- UTILITIES -----------------

string getTimestamp() {
    time_t now = time(0);
    char buf[80];
    tm *t = localtime(&now);
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", t);
    return string(buf);
}

string taskToJson(const Task& t) {
    return "  {\n"
           "    \"id\": " + to_string(t.id) + ",\n"
           "    \"description\": \"" + t.description + "\",\n"
           "    \"status\": \"" + t.status + "\",\n"
           "    \"createdAt\": \"" + t.createdAt + "\",\n"
           "    \"updatedAt\": \"" + t.updatedAt + "\"\n"
           "  }";
}

// ----------------- FILE HANDLING -----------------

vector<Task> loadTasks() {
    vector<Task> tasks;
    ifstream file("tasks.json");
    if (!file.is_open()) return tasks;

    string line;
    Task t;

    while (getline(file, line)) {
        if (line.find("\"id\"") != string::npos)
            t.id = stoi(line.substr(line.find(":") + 1));
        else if (line.find("\"description\"") != string::npos)
            t.description = line.substr(line.find("\"", 20) + 1,
                                         line.rfind("\"") - line.find("\"", 20) - 1);
        else if (line.find("\"status\"") != string::npos)
            t.status = line.substr(line.find("\"", 14) + 1,
                                   line.rfind("\"") - line.find("\"", 14) - 1);
        else if (line.find("\"createdAt\"") != string::npos)
            t.createdAt = line.substr(line.find("\"", 17) + 1,
                                      line.rfind("\"") - line.find("\"", 17) - 1);
        else if (line.find("\"updatedAt\"") != string::npos) {
            t.updatedAt = line.substr(line.find("\"", 17) + 1,
                                      line.rfind("\"") - line.find("\"", 17) - 1);
            tasks.push_back(t);
        }
    }
    return tasks;
}

void saveTasks(const vector<Task>& tasks) {
    ofstream file("tasks.json");
    file << "[\n";
    for (size_t i = 0; i < tasks.size(); i++) {
        file << taskToJson(tasks[i]);
        if (i != tasks.size() - 1) file << ",";
        file << "\n";
    }
    file << "]";
}

// ----------------- CORE FEATURES -----------------

void addTask(string desc) {
    vector<Task> tasks = loadTasks();
    int newId = tasks.empty() ? 1 : tasks.back().id + 1;
    string now = getTimestamp();

    tasks.push_back({newId, desc, "todo", now, now});
    saveTasks(tasks);

    cout << "Task added successfully (ID: " << newId << ")\n";
}

void updateTask(int id, string desc) {
    auto tasks = loadTasks();
    for (auto &t : tasks) {
        if (t.id == id) {
            t.description = desc;
            t.updatedAt = getTimestamp();
            saveTasks(tasks);
            cout << "Task updated\n";
            return;
        }
    }
    cout << "Task not found\n";
}

void deleteTask(int id) {
    auto tasks = loadTasks();
    for (auto it = tasks.begin(); it != tasks.end(); ++it) {
        if (it->id == id) {
            tasks.erase(it);
            saveTasks(tasks);
            cout << "Task deleted\n";
            return;
        }
    }
    cout << "Task not found\n";
}

void markTask(int id, string status) {
    auto tasks = loadTasks();
    for (auto &t : tasks) {
        if (t.id == id) {
            t.status = status;
            t.updatedAt = getTimestamp();
            saveTasks(tasks);
            cout << "Task marked as " << status << "\n";
            return;
        }
    }
    cout << "Task not found\n";
}

void listTasks(string filter = "") {
    auto tasks = loadTasks();
    for (auto &t : tasks) {
        if (filter.empty() || t.status == filter) {
            cout << "[" << t.id << "] "
                 << t.description
                 << " (" << t.status << ")\n";
        }
    }
}

// ----------------- CLI -----------------

int main(int argc, char* argv[]) {
    if (argc < 2) {
        cout << "Usage: task-cli <command>\n";
        return 1;
    }

    string cmd = argv[1];

    if (cmd == "add" && argc >= 3)
        addTask(argv[2]);

    else if (cmd == "update" && argc >= 4)
        updateTask(stoi(argv[2]), argv[3]);

    else if (cmd == "delete" && argc >= 3)
        deleteTask(stoi(argv[2]));

    else if (cmd == "mark-in-progress" && argc >= 3)
        markTask(stoi(argv[2]), "in-progress");

    else if (cmd == "mark-done" && argc >= 3)
        markTask(stoi(argv[2]), "done");

    else if (cmd == "list") {
        if (argc == 3)
            listTasks(argv[2]);
        else
            listTasks();
    }

    else
        cout << "Unknown command\n";

    return 0;
}
