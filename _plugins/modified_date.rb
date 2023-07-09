class ModifiedDateGenerator < Jekyll::Generator
    def generate(site)
        site.posts.docs.each do |post|
            post.data["modified_date"] = File.mtime(post.path)
        end
    end
end 